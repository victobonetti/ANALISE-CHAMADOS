"""Baseline por protótipos: classifica sem nenhum fine-tuning.

Mesmo método usado na demo do Space. Serve para dois fins: medir o piso de
qualidade antes de investir em rotulagem, e dar um número de referência contra
o qual o modelo com fine-tuning precisa ganhar para justificar o esforço.

Uso:
    python src/prototipos.py --sementes data/sementes.jsonl \
        --avaliar data/manifestacoes.jsonl
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from avaliacao import avaliar, curva_abstencao
from dados import carregar_jsonl, truncar_cabeca_cauda
from taxonomia import ROTULOS


class ClassificadorPrototipos:
    """Classificador por similaridade de cosseno a centroides de classe."""

    def __init__(self, modelo_base: str, max_tokens: int = 512, dispositivo: str | None = None):
        self.dispositivo = dispositivo or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_tokens = max_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(modelo_base)
        self.modelo = AutoModel.from_pretrained(modelo_base).eval().to(self.dispositivo)
        self.prototipos: torch.Tensor | None = None
        self.centro: torch.Tensor | None = None

    def embutir(self, textos: list[str], lote: int = 8) -> torch.Tensor:
        """Codifica textos pela média mascarada da última camada oculta.

        Args:
            textos: textos a codificar.
            lote: tamanho do lote de inferência.

        Returns:
            Tensor (n, hidden_size) em float32.
        """
        vetores = []
        for inicio in range(0, len(textos), lote):
            fatia = [
                truncar_cabeca_cauda(t, self.tokenizer, self.max_tokens)
                for t in textos[inicio : inicio + lote]
            ]
            entrada = self.tokenizer(
                fatia,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_tokens,
            ).to(self.dispositivo)
            with torch.inference_mode():
                oculto = self.modelo(**entrada).last_hidden_state
            mascara = entrada["attention_mask"].unsqueeze(-1).to(oculto.dtype)
            media = (oculto * mascara).sum(dim=1) / mascara.sum(dim=1).clamp(min=1e-9)
            vetores.append(media.float().cpu())
        return torch.cat(vetores)

    def ajustar(self, sementes: list) -> None:
        """Constrói um protótipo por classe a partir dos exemplos-semente.

        O centro do corpus é subtraído antes da normalização: sem isso, todos
        os textos de ouvidoria em português compartilham uma direção dominante
        e as similaridades ficam comprimidas perto de 1, sem discriminação.

        Args:
            sementes: manifestações anotadas que servem de referência.
        """
        vetores = self.embutir([s.texto for s in sementes])
        self.centro = vetores.mean(dim=0, keepdim=True)
        centrados = torch.nn.functional.normalize(vetores - self.centro, dim=-1)

        prototipos = []
        for rotulo in ROTULOS:
            indices = [i for i, s in enumerate(sementes) if rotulo in s.rotulos]
            if not indices:
                raise ValueError(f"nenhum exemplo-semente para a classe '{rotulo}'")
            proto = centrados[indices].mean(dim=0)
            prototipos.append(torch.nn.functional.normalize(proto, dim=-1))
        self.prototipos = torch.stack(prototipos)

    def prever(self, textos: list[str], temperatura: float = 0.05) -> np.ndarray:
        """Prevê a distribuição de probabilidade sobre as cinco classes.

        Args:
            textos: manifestações a classificar.
            temperatura: espalhamento do softmax sobre as similaridades.

        Returns:
            Matriz (n, 5) de probabilidades, na ordem de ROTULOS.

        Raises:
            RuntimeError: se `ajustar` ainda não tiver sido chamado.
        """
        if self.prototipos is None or self.centro is None:
            raise RuntimeError("chame ajustar() antes de prever()")

        vetores = self.embutir(textos)
        vetores = torch.nn.functional.normalize(vetores - self.centro, dim=-1)
        similaridades = vetores @ self.prototipos.T
        return torch.softmax(similaridades / max(temperatura, 1e-3), dim=-1).numpy()


def main() -> None:
    """Ajusta o baseline nas sementes e reporta as métricas no corpus indicado."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default="neuralmind/bert-base-portuguese-cased")
    parser.add_argument("--sementes", default="data/sementes.jsonl")
    parser.add_argument("--avaliar", default="data/manifestacoes.jsonl")
    parser.add_argument("--temperatura", type=float, default=0.05)
    argumentos = parser.parse_args()

    sementes = carregar_jsonl(argumentos.sementes)
    classificador = ClassificadorPrototipos(argumentos.modelo)
    classificador.ajustar(sementes)

    alvo = carregar_jsonl(argumentos.avaliar)
    if pathlib.Path(argumentos.avaliar).samefile(argumentos.sementes):
        print(
            "AVISO: avaliando sobre as próprias sementes — o número resultante "
            "é otimista e não estima desempenho fora da amostra.\n"
        )

    probabilidades = classificador.prever([m.texto for m in alvo], argumentos.temperatura)
    verdadeiros = [m.primaria for m in alvo]
    previstos = [ROTULOS[i] for i in probabilidades.argmax(axis=1)]

    print(avaliar(verdadeiros, previstos))
    print("\ncurva de abstenção (limiar / cobertura / macro-F1):")
    for limiar, cobertura, f1 in curva_abstencao(verdadeiros, probabilidades):
        print(f"  {limiar:.2f}   {cobertura:6.1%}   {f1:.4f}")


if __name__ == "__main__":
    main()
