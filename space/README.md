---
title: Albertina PT-BR — Triagem de Ouvidoria
emoji: 🏛️
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
python_version: "3.12"
short_description: Triagem de manifestacoes de ouvidoria com Albertina 1.5B
---

# Albertina 1.5B PT-BR — triagem de manifestações de ouvidoria

Demo do encoder [PORTULAN/albertina-1b5-portuguese-ptbr-encoder](https://huggingface.co/PORTULAN/albertina-1b5-portuguese-ptbr-encoder)
aplicado à classificação das cinco espécies de manifestação previstas na
Lei 13.460/2017: **elogio**, **sugestão**, **reclamação**, **denúncia** e
**solicitação**.

## O que este Space demonstra

O Albertina é um DeBERTa-v2 de 1.5B parâmetros pré-treinado apenas em
modelagem de linguagem mascarada. Ele **não** traz uma cabeça de classificação
treinada, então não existe "classificar com o Albertina" pronto para uso.

A aba de triagem implementa um *baseline por protótipos*, que extrai valor do
encoder sem nenhum dado rotulado:

1. Cada um dos 40 exemplos-semente é convertido em um vetor pela média
   mascarada da última camada oculta.
2. O centro do corpus é subtraído — sem isso, todo texto de ouvidoria em
   português compartilha uma direção dominante e as similaridades ficam
   comprimidas perto de 1.
3. Os vetores centrados são normalizados e promediados por classe, formando
   cinco protótipos.
4. A manifestação de entrada percorre o mesmo caminho e é atribuída à classe
   de maior similaridade de cosseno.

Quando a margem entre a primeira e a segunda classe fica abaixo de 30%, a
demo recomenda triagem humana em vez de cravar um rótulo.

A segunda aba expõe o preenchimento de máscara, a tarefa nativa do modelo.

## Limites

- **Isto não substitui fine-tuning.** O baseline por protótipos serve para
  medir o piso de qualidade antes de investir em rotulagem. Um encoder com
  cabeça treinada em alguns milhares de exemplos supera esta abordagem com
  folga, especialmente na fronteira reclamação/denúncia.
- **Não use para decisão automatizada** sobre manifestações reais. Classificar
  uma denúncia como reclamação tem consequências processuais — sigilo do
  denunciante e encaminhamento à corregedoria deixam de ser acionados.
- **Não envie dados pessoais.** Manifestações reais contêm CPF, nome e
  endereço, e denúncias são sigilosas.
- Textos acima de 512 tokens são truncados preservando cabeça e cauda, já que
  o pedido concreto costuma estar no fim.
