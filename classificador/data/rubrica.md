# Rubrica de anotação — manifestações de ouvidoria

Esta rubrica é o contrato entre os anotadores. Sem ela, dois anotadores
discordam em cerca de um terço dos casos de fronteira e o modelo aprende o
ruído.

Classes: `reclamacao`, `elogio`, `duvida`, `denuncia`, `sugestao`.

## Procedimento

Para cada manifestação, responda **nesta ordem** e pare na primeira que for sim:

1. **Relata irregularidade, ilegalidade, corrupção ou conduta antiética por
   parte da administração ou de quem age em seu nome?** → `denuncia`
2. **Expressa insatisfação com serviço, produto ou atendimento que não ocorreu
   como esperado?** → `reclamacao`
3. **Propõe uma melhoria para um processo, serviço ou estrutura?** → `sugestao`
4. **Pede um esclarecimento sobre como algo funciona, qual o procedimento ou
   qual o andamento?** → `duvida`
5. **Reconhece um bom atendimento, serviço de qualidade ou conduta exemplar?**
   → `elogio`

Marque **todos** os rótulos aplicáveis, não apenas o primeiro. A classe
primária é derivada pela ordem de precedência acima
(`taxonomia.classe_primaria`). A anotação multirrótulo existe porque o texto
real quase sempre mistura intenções, e forçar rótulo único injeta ruído.

## Lacuna conhecida: pedidos de providência

A taxonomia não tem classe para o **pedido de providência** — "solicito a poda
da árvore", "peço a troca da lâmpada do poste", "requeiro a limpeza do terreno
baldio". Não é dúvida (não se pergunta nada), não é sugestão (não propõe mudar
como a administração opera, apenas pede que ela faça o que já lhe compete) e
não é reclamação enquanto não houver insatisfação com algo já ocorrido.

Numa ouvidoria municipal esse é tipicamente o maior volume isolado de entrada.
Enquanto a lacuna não for decidida, anote esses casos com
`descartar: true` e o motivo `"pedido de providência"`, para que fiquem fora do
treino e possam ser recuperados depois.

As três saídas possíveis, quando for hora de decidir:

1. Acrescentar `solicitacao` como sexta classe — cobre o caso sem distorcer as
   outras cinco.
2. Absorver em `duvida`, redefinindo-a como "solicitação" no sentido amplo
   (pedido de providência *ou* de esclarecimento). É reverter para a taxonomia
   anterior sob outro nome.
3. Absorver em `reclamacao`, tratando todo pedido como insatisfação implícita.
   **Não recomendado**: infla a classe mais sensível a prazo e mistura dois
   fluxos de trabalho distintos.

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

## Reclamação × dúvida

`duvida` exige que **não haja insatisfação com algo já ocorrido**. A pergunta
tem de ser o propósito da manifestação, não a queixa disfarçada de pergunta.

- *"Qual o prazo para análise do meu pedido de licença?"* → `duvida`.
- *"Já se passaram noventa dias e ninguém analisou meu pedido de licença. Qual
  o prazo, afinal?"* → `reclamacao`. A pergunta é retórica; o núcleo é a
  demora.
- *"Como funciona a fila da creche?"* → `duvida`.
- *"Minha filha está na fila da creche há dois anos enquanto vizinhas que se
  inscreveram depois já conseguiram vaga."* → `denuncia` + `reclamacao`, pela
  alegação de favorecimento.

## Sugestão × dúvida

- `duvida` pergunta **como algo funciona hoje**.
- `sugestao` propõe **mudar como funciona**.

- *"O portal permite agendamento aos sábados?"* → `duvida`.
- *"Proponho que o portal passe a permitir agendamento aos sábados."* →
  `sugestao`.

Quando o texto faz as duas coisas — *"o portal não permite agendar aos
sábados? deveria permitir"* — marque ambos; a precedência resolve para
`sugestao`.

## Elogio junto de outra coisa

Cortesia de abertura não é elogio. *"Bom dia, parabéns pelo trabalho de vocês.
Venho reclamar que..."* → só `reclamacao`. Marque `elogio` apenas quando o
reconhecimento for um propósito da manifestação, não fórmula de polidez.

## Casos que não entram na taxonomia

Textos vazios, testes ("teste 123"), duplicatas e mensagens sem conteúdo
identificável devem ser marcados com `descartar: true` e ficam fora do treino.
Não force um dos cinco rótulos sobre lixo — isso ensina o modelo a inventar.
