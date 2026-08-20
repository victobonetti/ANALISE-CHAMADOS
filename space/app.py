"""Demo do Albertina 1.5B PT-BR aplicado à triagem de manifestações de ouvidoria.

Duas abas: a tarefa nativa do modelo (preenchimento de máscara) e um
classificador por protótipos que usa os embeddings do encoder para separar as
cinco classes da Lei 13.460/2017 sem nenhum fine-tuning.
"""

import spaces  # precisa vir antes de torch — faz o monkey-patch de torch.cuda

import json
import pathlib

import gradio as gr
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

from taxonomia import DESCRICOES, ROTULOS

MODELO = "PORTULAN/albertina-1b5-portuguese-ptbr-encoder"
MAX_TOKENS = 512
LIMIAR_ABSTENCAO = 0.30

tokenizer = AutoTokenizer.from_pretrained(MODELO)
modelo = AutoModelForMaskedLM.from_pretrained(MODELO, dtype=torch.bfloat16)
modelo.eval().to("cuda")

SEMENTES = [
    json.loads(linha)
    for linha in pathlib.Path("sementes.jsonl").read_text(encoding="utf-8").splitlines()
    if linha.strip()
]

# Preenchido na primeira chamada de classificar(); depende da GPU, que só existe
# dentro de uma função decorada com @spaces.GPU.
_protótipos: dict[str, torch.Tensor] = {}
_centro: torch.Tensor | None = None


def truncar_cabeca_cauda(texto: str, max_tokens: int = MAX_TOKENS) -> str:
    """Trunca preservando início e fim do texto, em vez de só o início.

    Manifestações longas costumam trazer o contexto no começo e o pedido
    concreto no fim; o truncamento simples do transformers descartaria
    justamente a parte que decide o rótulo.

    Args:
        texto: texto da manifestação.
        max_tokens: orçamento total de tokens, incluindo os especiais.

    Returns:
        O texto original, se couber, ou a concatenação de sua cabeça e cauda.
    """
    ids = tokenizer.encode(texto, add_special_tokens=False)
    util = max_tokens - 2  # [CLS] e [SEP]
    if len(ids) <= util:
        return texto
    cabeca = util // 4
    cauda = util - cabeca
    return tokenizer.decode(ids[:cabeca]) + " [...] " + tokenizer.decode(ids[-cauda:])


def _embutir(textos: list[str]) -> torch.Tensor:
    """Codifica textos em vetores por média mascarada da última camada oculta.

    Args:
        textos: textos já truncados.

    Returns:
        Tensor (n, hidden_size) em float32, sem normalização.
    """
    lote = tokenizer(
        textos,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=MAX_TOKENS,
    ).to("cuda")
    with torch.inference_mode():
        saida = modelo(**lote, output_hidden_states=True)
    oculto = saida.hidden_states[-1]
    mascara = lote["attention_mask"].unsqueeze(-1).to(oculto.dtype)
    media = (oculto * mascara).sum(dim=1) / mascara.sum(dim=1).clamp(min=1e-9)
    return media.float()


def _preparar_protótipos() -> None:
    """Calcula um protótipo por classe a partir dos exemplos-semente.

    O centro do corpus é subtraído antes da normalização: sem isso, todos os
    textos de ouvidoria em português compartilham uma direção dominante e as
    similaridades ficam comprimidas perto de 1, sem poder discriminante.
    """
    global _centro

    if _protótipos:
        return

    textos = [truncar_cabeca_cauda(s["texto"]) for s in SEMENTES]
    vetores = _embutir(textos)
    _centro = vetores.mean(dim=0, keepdim=True)
    centrados = torch.nn.functional.normalize(vetores - _centro, dim=-1)

    for rotulo in ROTULOS:
        indices = [i for i, s in enumerate(SEMENTES) if rotulo in s["rotulos"]]
        proto = centrados[indices].mean(dim=0)
        _protótipos[rotulo] = torch.nn.functional.normalize(proto, dim=-1)


@spaces.GPU(duration=90)
def classificar(texto: str, temperatura: float = 0.05) -> tuple[dict, str]:
    """Classifica uma manifestação de ouvidoria nas cinco classes da Lei 13.460.

    Baseline por similaridade de protótipos: o encoder Albertina converte o
    texto em um vetor, que é comparado por cosseno ao centroide de cada classe.
    Não há fine-tuning — serve para medir o piso de qualidade antes de investir
    em rotulagem, não para produção.

    Args:
        texto: a manifestação a classificar, em português.
        temperatura: espalhamento do softmax sobre as similaridades. Valores
            menores tornam a distribuição mais concentrada na classe vencedora.

    Returns:
        Um par com as probabilidades por classe e um parecer textual sobre a
        confiança da decisão.
    """
    if not texto or not texto.strip():
        return {}, "Informe o texto da manifestação."

    _preparar_protótipos()

    vetor = _embutir([truncar_cabeca_cauda(texto)])
    vetor = torch.nn.functional.normalize(vetor - _centro, dim=-1)

    similaridades = torch.stack([_protótipos[r] @ vetor[0] for r in ROTULOS])
    probabilidades = torch.softmax(similaridades / max(temperatura, 1e-3), dim=0)

    pontuacoes = {r: probabilidades[i].item() for i, r in enumerate(ROTULOS)}
    vencedor = max(pontuacoes, key=pontuacoes.get)
    margem = sorted(pontuacoes.values(), reverse=True)
    confianca = margem[0] - margem[1]

    if confianca < LIMIAR_ABSTENCAO:
        parecer = (
            f"**Triagem humana recomendada.** A margem entre a primeira e a "
            f"segunda classe é de apenas {confianca:.1%}, abaixo do limiar de "
            f"{LIMIAR_ABSTENCAO:.0%}.\n\n"
            f"Hipótese principal: **{vencedor}** — {DESCRICOES[vencedor]}"
        )
    else:
        parecer = (
            f"**{vencedor}** ({pontuacoes[vencedor]:.1%}, margem de "
            f"{confianca:.1%})\n\n{DESCRICOES[vencedor]}"
        )
    return pontuacoes, parecer


@spaces.GPU(duration=60)
def preencher_mascara(texto: str) -> dict:
    """Prevê o token oculto por [MASK], a tarefa nativa de pré-treino do modelo.

    Args:
        texto: frase em português contendo exatamente um marcador [MASK].

    Returns:
        As dez continuações mais prováveis, com suas probabilidades.
    """
    if "[MASK]" not in texto:
        raise gr.Error("O texto precisa conter o marcador [MASK].")

    lote = tokenizer(texto, return_tensors="pt", truncation=True, max_length=MAX_TOKENS)
    lote = lote.to("cuda")
    posicao = (lote["input_ids"][0] == tokenizer.mask_token_id).nonzero()
    if len(posicao) != 1:
        raise gr.Error("Use exatamente um marcador [MASK].")

    with torch.inference_mode():
        logits = modelo(**lote).logits

    probabilidades = torch.softmax(logits[0, posicao.item()].float(), dim=-1)
    topo = probabilidades.topk(10)
    return {
        tokenizer.decode(indice).strip(): valor.item()
        for valor, indice in zip(topo.values, topo.indices)
    }


AVISO = """
> **O que este Space é e o que não é.** O Albertina é um encoder pré-treinado
> apenas em modelagem de linguagem mascarada — ele não vem com cabeça de
> classificação treinada. A aba de triagem abaixo é um *baseline por
> protótipos*: compara o texto aos centroides de 40 exemplos-semente no espaço
> de embeddings. Funciona sem nenhum dado rotulado e serve para calibrar
> expectativas, mas fica bem abaixo de um modelo com fine-tuning. Não use para
> decisão automatizada sobre manifestações reais.
"""

EXEMPLOS_CLASSIFICACAO = [
    ["Estou há mais de três horas na fila do posto de saúde com senha marcada para as 8h e ninguém foi chamado."],
    ["O fiscal exigiu pagamento em espécie para liberar o alvará, dizendo que sem isso o processo demoraria meses."],
    ["Solicito a poda das árvores da Rua das Acácias, cujos galhos encostam na rede elétrica."],
    ["Parabenizo a enfermeira Marta, que explicou cada etapa do exame com muita paciência."],
    ["Proponho que o portal permita agendamento aos sábados pela manhã para reduzir as filas."],
    ["O servidor não me atendeu porque exigiu um valor por fora para dar andamento ao processo."],
]

EXEMPLOS_MASCARA = [
    ["A culinária portuguesa é rica em sabores e [MASK], tornando-se um dos maiores tesouros do país."],
    ["O cidadão registrou uma [MASK] na ouvidoria do município."],
    ["A administração pública deve obedecer ao princípio da [MASK]."],
]

with gr.Blocks(title="Albertina 1.5B — triagem de ouvidoria") as demo:
    gr.Markdown("# Albertina 1.5B PT-BR — triagem de manifestações de ouvidoria")
    gr.Markdown(AVISO)

    with gr.Tab("Triagem da manifestação"):
        with gr.Row():
            with gr.Column():
                entrada = gr.Textbox(
                    label="Manifestação",
                    lines=8,
                    placeholder="Cole aqui o texto do chamado...",
                )
                temperatura = gr.Slider(
                    0.01, 0.30, value=0.05, step=0.01,
                    label="Temperatura",
                    info="Menor = distribuição mais concentrada na classe vencedora.",
                )
                botao = gr.Button("Classificar", variant="primary")
            with gr.Column():
                saida_rotulos = gr.Label(label="Probabilidade por classe", num_top_classes=5)
                saida_parecer = gr.Markdown(label="Parecer")

        botao.click(classificar, [entrada, temperatura], [saida_rotulos, saida_parecer])
        gr.Examples(
            EXEMPLOS_CLASSIFICACAO,
            inputs=[entrada],
            outputs=[saida_rotulos, saida_parecer],
            fn=classificar,
            cache_examples=True,
            cache_mode="lazy",
        )

        gr.Markdown(
            "### As cinco classes\n"
            + "\n".join(f"- **{r}** — {DESCRICOES[r]}" for r in ROTULOS)
        )

    with gr.Tab("Preenchimento de máscara"):
        gr.Markdown(
            "A tarefa nativa do modelo. Útil para confirmar que o encoder de "
            "fato entende o português do Brasil."
        )
        entrada_mascara = gr.Textbox(
            label="Frase com [MASK]",
            lines=3,
            value="O cidadão registrou uma [MASK] na ouvidoria do município.",
        )
        botao_mascara = gr.Button("Prever", variant="primary")
        saida_mascara = gr.Label(label="Tokens mais prováveis", num_top_classes=10)

        botao_mascara.click(preencher_mascara, [entrada_mascara], [saida_mascara])
        gr.Examples(
            EXEMPLOS_MASCARA,
            inputs=[entrada_mascara],
            outputs=[saida_mascara],
            fn=preencher_mascara,
            cache_examples=True,
            cache_mode="lazy",
        )

if __name__ == "__main__":
    # ssr_mode=False: o servidor SSR do Gradio responde 405 às chamadas de API
    # e polui o log sem afetar o resultado.
    demo.launch(mcp_server=True, ssr_mode=False)
