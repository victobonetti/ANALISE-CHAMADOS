# Rubrica de anotação — manifestações de ouvidoria

Base legal: Lei 13.460/2017, art. 2º. Esta rubrica é o contrato entre os
anotadores. Sem ela, dois anotadores discordam em cerca de um terço dos casos
de fronteira e o modelo aprende o ruído.

## Procedimento

Para cada manifestação, responda **nesta ordem** e pare na primeira que for sim:

1. **Relata irregularidade, ilegalidade, corrupção ou conduta antiética por
   parte da administração ou de quem age em seu nome?** → `denuncia`
2. **Expressa insatisfação com serviço, produto ou atendimento que não ocorreu
   como esperado?** → `reclamacao`
3. **Pede uma providência concreta ou um esclarecimento?** → `solicitacao`
4. **Propõe uma melhoria para um processo, serviço ou estrutura?** → `sugestao`
5. **Reconhece um bom atendimento, serviço de qualidade ou conduta exemplar?**
   → `elogio`

Marque **todos** os rótulos aplicáveis, não apenas o primeiro. A classe
primária é derivada pela ordem de precedência acima (`taxonomia.classe_primaria`).
A anotação multirrótulo existe porque o texto real quase sempre mistura
intenções, e forçar rótulo único injeta ruído.

## A fronteira crítica: reclamação × denúncia

É onde o modelo mais erra e onde o erro custa mais caro. O critério não é a
intensidade da insatisfação, e sim **a natureza do que é relatado**.

| Sinal | Classe |
|---|---|
| O serviço foi ruim, lento, malfeito ou o servidor foi grosseiro | `reclamacao` |
| Houve vantagem indevida, favorecimento, desvio, fraude ou quebra de dever funcional | `denuncia` |

Casos de fronteira resolvidos:

- *"O servidor me atendeu mal e com má vontade."* → `reclamacao`.
  Conduta desagradável não é conduta antiética.
- *"O servidor só me atendeu depois que ofereci um agrado."* → `denuncia`.
  Há vantagem indevida, independentemente do tom da manifestação.
- *"Meu processo está parado há oito meses."* → `reclamacao`.
  Ineficiência, sem alegação de irregularidade.
- *"Meu processo está parado há oito meses, mas o do meu vizinho, que é primo
  do diretor, saiu em uma semana."* → `denuncia`.
  A comparação alega favorecimento; é o núcleo do relato, não um detalhe.
- *"A obra ficou malfeita e já está rachando."* → `reclamacao`.
  Má execução, sem afirmação sobre o contrato.
- *"A obra usou material inferior ao previsto no contrato e a medição foi
  atestada assim mesmo."* → `denuncia`.

**Na dúvida entre as duas, marque ambas.** A precedência põe `denuncia` como
primária, e o custo de tratar uma reclamação como denúncia (trabalho extra de
triagem) é muito menor que o inverso (perda de sigilo e de prazo).

## Reclamação × solicitação

`solicitacao` é a classe **residual** dos pedidos: só se aplica quando não há
insatisfação com algo que já ocorreu.

- *"Solicito a troca da lâmpada do poste."* → `solicitacao`.
- *"A lâmpada está queimada há dois meses e ninguém veio trocar, apesar dos
  três chamados que abri."* → `reclamacao` + `solicitacao`.

## Sugestão × solicitação

- `solicitacao` pede que a administração **execute algo que já lhe compete**.
- `sugestao` propõe **mudar como ela opera**.

- *"Peço a poda das árvores da minha rua."* → `solicitacao`.
- *"Proponho um calendário anual de poda preventiva por bairro."* → `sugestao`.

## Elogio junto de outra coisa

Cortesia de abertura não é elogio. *"Bom dia, parabéns pelo trabalho de vocês.
Venho reclamar que..."* → só `reclamacao`. Marque `elogio` apenas quando o
reconhecimento for um propósito da manifestação, não fórmula de polidez.

## Casos que não entram na taxonomia

Textos vazios, testes ("teste 123"), duplicatas e mensagens sem conteúdo
identificável devem ser marcados com `descartar: true` e ficam fora do treino.
Não force um dos cinco rótulos sobre lixo — isso ensina o modelo a inventar.
