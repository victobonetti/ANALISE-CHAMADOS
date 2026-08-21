# Classificador de manifestações de ouvidoria

Triagem automática de manifestações de ouvidoria em cinco classes:
**reclamação**, **elogio**, **dúvida**, **denúncia** e **sugestão**.

A taxonomia é inspirada na Lei 13.460/2017, mas não idêntica: no lugar da
`solicitação` legal, que engloba pedido de providência *e* de esclarecimento,
usamos `dúvida`, restrita ao esclarecimento. A lacuna que isso abre está
documentada em [`data/rubrica.md`](data/rubrica.md).

## Estrutura

```
configs/base.yaml       hiperparâmetros e escolha do encoder
data/rubrica.md         contrato de anotação, com os casos de fronteira resolvidos
data/sementes.jsonl     40 exemplos de referência (8 por classe)
src/taxonomia.py        rótulos, precedência e pesos de custo — fonte única de verdade
src/dados.py            carga, validação e partição estratificada
src/prototipos.py       baseline sem fine-tuning, por similaridade de protótipos
src/treino.py           fine-tuning multirrótulo com BCE ponderada
src/avaliacao.py        macro-F1, matriz de confusão, vazamento e curva de abstenção
```

## Decisões de modelagem

**Multirrótulo, não multiclasse.** O texto real mistura intenções — *"o portal
não permite agendar aos sábados? deveria permitir"*. A cabeça usa sigmoide por
classe; a classe
primária é derivada depois pela precedência
`denúncia > reclamação > sugestão > dúvida > elogio`.

**Custo assimétrico embutido.** `PESO_CLASSE` dá peso 3 à denúncia na loss.
Classificar uma denúncia como reclamação suprime o sigilo do denunciante e o
encaminhamento à corregedoria; o erro inverso apenas gera triagem extra.

**Macro-F1 e vazamento, nunca acurácia.** Reclamação e dúvida dominam o
volume, então um modelo que só as prevê já acerta a maior parte. O
`avaliacao.Resultado` reporta `vazamento_denuncia` — a fração de denúncias
verdadeiras que escapou para outra classe — como métrica de risco. Um modelo
com macro-F1 de 0,73 e vazamento de 100% existe, e é inaceitável.

**Abstenção como parte do produto.** `curva_abstencao` traça cobertura contra
qualidade ao variar a margem mínima entre a primeira e a segunda classe. O
ponto de operação é escolhido pela precisão que a ouvidoria exige; o volume
restante segue para triagem humana.

**Truncamento cabeça+cauda.** O limite de 512 tokens do encoder descartaria o
fim do texto, onde costuma estar o pedido concreto. `truncar_cabeca_cauda`
preserva o primeiro quarto e os últimos três quartos do orçamento.

## Como usar

```bash
pip install -r requirements.txt

# 1. Piso de qualidade, sem nenhum dado rotulado
python src/prototipos.py --sementes data/sementes.jsonl --avaliar data/manifestacoes.jsonl

# 2. Fine-tuning, depois de substituir data/manifestacoes.jsonl pelo corpus real
python src/treino.py --config configs/base.yaml
```

Formato do corpus, um objeto JSON por linha:

```json
{"id": "2024-11987", "texto": "...", "rotulos": ["reclamacao", "duvida"]}
```

`data/manifestacoes.jsonl` hoje é uma cópia das sementes, apenas para o
pipeline rodar de ponta a ponta. **Os números que ele produz não significam
nada** — o modelo seria avaliado nos mesmos exemplos que o definiram.

## Escolha do encoder

O padrão é o **BERTimbau base** (110M): treina em minutos, serve em CPU, e é o
melhor ponto de partida. Os encoders Albertina (100M / 900M / 1.5B) estão
listados em `configs/base.yaml`. O 1.5B exige A100 ou H100 com gradient
checkpointing, e o ganho típico sobre o BERTimbau é de poucos pontos de
macro-F1 — não compensa antes de o corpus passar de ~10 mil exemplos.

## O caminho até produção

1. **Rubrica antes de dados.** `data/rubrica.md` é o que faz dois anotadores
   concordarem na fronteira reclamação/denúncia. Sem ela o modelo aprende ruído.
2. **Não confie no rótulo do formulário.** A classificação escolhida pelo
   próprio cidadão é fortemente enviesada para "reclamação" e não serve como
   verdade de referência sem revisão.
3. **Rotule com apoio de LLM, revise o que for duvidoso.** Um LLM pré-rotula o
   corpus; o humano revisa os casos de baixa confiança e as fronteiras. Corta a
   maior parte do esforço.
4. **Anonimize antes de qualquer chamada externa.** Manifestações contêm CPF,
   nome e endereço, e denúncias são sigilosas — o que sustenta manter o modelo
   final on-premise.
5. **Meça a concordância entre anotadores** (kappa de Cohen) antes de treinar.
   Se os humanos concordam pouco, o teto do modelo já está definido.
