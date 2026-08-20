"""Métricas de avaliação para a triagem de manifestações.

Acurácia é enganosa neste problema: `solicitacao` e `reclamacao` costumam somar
80% do volume, e um modelo que só as prevê já acerta 80%. Tudo aqui é orientado
a macro-F1, recall por classe e ao custo assimétrico de perder uma denúncia.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from taxonomia import ROTULOS, ROTULO2ID


@dataclass
class Resultado:
    """Resumo de uma avaliação.

    Attributes:
        macro_f1: média não ponderada do F1 por classe.
        f1_por_classe: F1 de cada classe, na ordem de ROTULOS.
        recall_por_classe: recall de cada classe.
        precisao_por_classe: precisão de cada classe.
        matriz_confusao: linhas são o rótulo verdadeiro, colunas o previsto.
        vazamento_denuncia: fração das denúncias verdadeiras classificadas
            como qualquer outra coisa. É a métrica de risco do sistema.
        cobertura: fração dos casos decididos automaticamente, quando há
            abstenção; 1.0 se todos foram decididos.
    """

    macro_f1: float
    f1_por_classe: dict[str, float]
    recall_por_classe: dict[str, float]
    precisao_por_classe: dict[str, float]
    matriz_confusao: np.ndarray
    vazamento_denuncia: float
    cobertura: float = 1.0

    def __str__(self) -> str:
        linhas = [
            f"macro-F1: {self.macro_f1:.4f}   cobertura: {self.cobertura:.1%}",
            f"vazamento de denúncia: {self.vazamento_denuncia:.1%}",
            "",
            f"{'classe':<14}{'P':>8}{'R':>8}{'F1':>8}",
        ]
        for rotulo in ROTULOS:
            linhas.append(
                f"{rotulo:<14}"
                f"{self.precisao_por_classe[rotulo]:>8.3f}"
                f"{self.recall_por_classe[rotulo]:>8.3f}"
                f"{self.f1_por_classe[rotulo]:>8.3f}"
            )
        linhas += ["", "matriz de confusão (linha = verdadeiro):", self._matriz_texto()]
        return "\n".join(linhas)

    def _matriz_texto(self) -> str:
        cabecalho = " " * 14 + "".join(f"{r[:6]:>8}" for r in ROTULOS)
        corpo = [
            f"{ROTULOS[i]:<14}" + "".join(f"{v:>8d}" for v in linha)
            for i, linha in enumerate(self.matriz_confusao)
        ]
        return "\n".join([cabecalho, *corpo])


def avaliar(
    verdadeiros: list[str],
    previstos: list[str],
    abstencoes: list[bool] | None = None,
) -> Resultado:
    """Calcula as métricas de triagem.

    Args:
        verdadeiros: rótulos de referência.
        previstos: rótulos previstos pelo modelo.
        abstencoes: para cada caso, se o modelo se absteve. Casos com abstenção
            saem do cálculo — a premissa é que vão para triagem humana e serão
            resolvidos corretamente — mas reduzem a cobertura.

    Returns:
        O resultado consolidado.

    Raises:
        ValueError: se as listas tiverem comprimentos diferentes.
    """
    if len(verdadeiros) != len(previstos):
        raise ValueError("verdadeiros e previstos têm comprimentos diferentes")
    if abstencoes is not None and len(abstencoes) != len(verdadeiros):
        raise ValueError("abstencoes tem comprimento diferente de verdadeiros")

    total = len(verdadeiros)
    if abstencoes is None:
        abstencoes = [False] * total

    pares = [
        (v, p) for v, p, a in zip(verdadeiros, previstos, abstencoes) if not a
    ]
    cobertura = len(pares) / total if total else 0.0
    if not pares:
        vazio = {r: 0.0 for r in ROTULOS}
        n = len(ROTULOS)
        return Resultado(0.0, vazio, vazio, vazio, np.zeros((n, n), int), 0.0, 0.0)

    n = len(ROTULOS)
    matriz = np.zeros((n, n), dtype=int)
    for verdadeiro, previsto in pares:
        matriz[ROTULO2ID[verdadeiro], ROTULO2ID[previsto]] += 1

    precisao, recall, f1 = {}, {}, {}
    for rotulo in ROTULOS:
        i = ROTULO2ID[rotulo]
        vp = int(matriz[i, i])
        fp = int(matriz[:, i].sum()) - vp
        fn = int(matriz[i, :].sum()) - vp
        precisao[rotulo] = vp / (vp + fp) if vp + fp else 0.0
        recall[rotulo] = vp / (vp + fn) if vp + fn else 0.0
        soma = precisao[rotulo] + recall[rotulo]
        f1[rotulo] = 2 * precisao[rotulo] * recall[rotulo] / soma if soma else 0.0

    i_denuncia = ROTULO2ID["denuncia"]
    denuncias = int(matriz[i_denuncia, :].sum())
    vazamento = (
        1.0 - matriz[i_denuncia, i_denuncia] / denuncias if denuncias else 0.0
    )

    return Resultado(
        macro_f1=float(np.mean(list(f1.values()))),
        f1_por_classe=f1,
        recall_por_classe=recall,
        precisao_por_classe=precisao,
        matriz_confusao=matriz,
        vazamento_denuncia=float(vazamento),
        cobertura=cobertura,
    )


def curva_abstencao(
    verdadeiros: list[str],
    probabilidades: np.ndarray,
    limiares: list[float] | None = None,
) -> list[tuple[float, float, float]]:
    """Traça o compromisso entre cobertura e qualidade ao variar o limiar.

    É essa curva que define o ponto de operação em produção: escolhe-se o
    limiar que entrega a precisão exigida pela ouvidoria, e o resto do volume
    segue para triagem humana.

    Args:
        verdadeiros: rótulos de referência.
        probabilidades: matriz (n, 5) com a distribuição prevista por caso.
        limiares: margens mínimas entre a primeira e a segunda classe. Padrão:
            de 0.0 a 0.6 em passos de 0.05.

    Returns:
        Uma tupla (limiar, cobertura, macro_f1) por limiar avaliado.
    """
    if limiares is None:
        limiares = [round(0.05 * i, 2) for i in range(13)]

    ordenadas = np.sort(probabilidades, axis=1)
    margens = ordenadas[:, -1] - ordenadas[:, -2]
    previstos = [ROTULOS[i] for i in probabilidades.argmax(axis=1)]

    curva = []
    for limiar in limiares:
        abstencoes = [bool(m < limiar) for m in margens]
        resultado = avaliar(verdadeiros, previstos, abstencoes)
        curva.append((limiar, resultado.cobertura, resultado.macro_f1))
    return curva
