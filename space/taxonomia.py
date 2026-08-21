"""Taxonomia das manifestações de ouvidoria (Lei 13.460/2017, art. 2º).

Este módulo é a fonte única de verdade sobre os rótulos: é importado tanto pelo
treino quanto pela demo do Space. Alterar a ordem de ROTULOS invalida qualquer
checkpoint já treinado, porque o índice do rótulo vira o índice do logit.
"""

from __future__ import annotations

ROTULOS: tuple[str, ...] = (
    "reclamacao",
    "elogio",
    "duvida",
    "denuncia",
    "sugestao",
)

ID2ROTULO: dict[int, str] = dict(enumerate(ROTULOS))
ROTULO2ID: dict[str, int] = {r: i for i, r in enumerate(ROTULOS)}

DESCRICOES: dict[str, str] = {
    "elogio": (
        "Reconhece e valoriza um bom atendimento, um serviço público de "
        "qualidade ou a conduta exemplar de um servidor."
    ),
    "sugestao": (
        "Apresenta uma proposta de melhoria para otimizar um processo, "
        "serviço ou estrutura do governo."
    ),
    "reclamacao": (
        "Demonstra insatisfação com um serviço, produto ou atendimento que "
        "não ocorreu como o esperado."
    ),
    "denuncia": (
        "Relata uma irregularidade, ilegalidade, ato de corrupção ou conduta "
        "antiética dentro da administração pública."
    ),
    "duvida": (
        "Pedido de esclarecimento sobre um serviço, um procedimento ou o "
        "andamento de um processo, sem insatisfação com algo já ocorrido."
    ),
}

# Ordem de precedência para derivar a classe primária quando o texto carrega
# mais de uma intenção (o caso comum: "reclamo do atraso E pergunto o prazo").
# Denúncia vem primeiro porque é a única com consequência processual própria:
# sigilo do denunciante e encaminhamento à corregedoria. Dúvida vem quase por
# último por ser a menos acionável: quem reclama e de passagem pergunta algo
# está reclamando.
PRECEDENCIA: tuple[str, ...] = (
    "denuncia",
    "reclamacao",
    "sugestao",
    "duvida",
    "elogio",
)

# Custo relativo de errar. Usado como peso na loss e para escolher o limiar de
# abstenção por classe. Deixar passar uma denúncia como reclamação é o erro
# mais caro do sistema; o inverso apenas gera trabalho extra de triagem.
PESO_CLASSE: dict[str, float] = {
    "reclamacao": 1.0,
    "elogio": 1.0,
    "duvida": 1.0,
    "denuncia": 3.0,
    "sugestao": 1.0,
}


def classe_primaria(rotulos: list[str]) -> str:
    """Reduz um conjunto de rótulos multirrótulo à classe primária.

    Args:
        rotulos: rótulos atribuídos ao texto, em qualquer ordem.

    Returns:
        O rótulo de maior precedência entre os informados.
    """
    if not rotulos:
        raise ValueError("lista de rótulos vazia")
    desconhecidos = set(rotulos) - set(ROTULOS)
    if desconhecidos:
        raise ValueError(f"rótulos fora da taxonomia: {sorted(desconhecidos)}")
    return next(r for r in PRECEDENCIA if r in rotulos)
