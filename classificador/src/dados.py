"""Carga, validação e particionamento do corpus de manifestações."""

from __future__ import annotations

import json
import pathlib
import random
from dataclasses import dataclass, field

from taxonomia import ROTULOS, classe_primaria


@dataclass
class Manifestacao:
    """Uma manifestação anotada.

    Attributes:
        texto: conteúdo da manifestação.
        rotulos: todos os rótulos aplicáveis, conforme a rubrica multirrótulo.
        id: identificador de origem, quando houver.
    """

    texto: str
    rotulos: list[str]
    id: str | None = None

    @property
    def primaria(self) -> str:
        """O rótulo de maior precedência entre os atribuídos."""
        return classe_primaria(self.rotulos)

    def vetor_multirrotulo(self) -> list[float]:
        """Alvo binário por classe, na ordem de ROTULOS."""
        return [1.0 if r in self.rotulos else 0.0 for r in ROTULOS]


@dataclass
class Particoes:
    """Divisão treino/validação/teste."""

    treino: list[Manifestacao] = field(default_factory=list)
    validacao: list[Manifestacao] = field(default_factory=list)
    teste: list[Manifestacao] = field(default_factory=list)


def carregar_jsonl(caminho: str | pathlib.Path) -> list[Manifestacao]:
    """Lê um arquivo JSONL de manifestações anotadas.

    Linhas marcadas com `descartar: true` são ignoradas, conforme a rubrica.

    Args:
        caminho: arquivo com um objeto JSON por linha, contendo ao menos as
            chaves `texto` e `rotulos`.

    Returns:
        As manifestações válidas encontradas.

    Raises:
        ValueError: se alguma linha trouxer rótulo fora da taxonomia ou lista
            de rótulos vazia.
    """
    itens: list[Manifestacao] = []
    for numero, linha in enumerate(
        pathlib.Path(caminho).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not linha.strip():
            continue
        registro = json.loads(linha)
        if registro.get("descartar"):
            continue

        rotulos = registro.get("rotulos") or []
        if not rotulos:
            raise ValueError(f"{caminho}:{numero} — manifestação sem rótulos")
        desconhecidos = set(rotulos) - set(ROTULOS)
        if desconhecidos:
            raise ValueError(
                f"{caminho}:{numero} — rótulos fora da taxonomia: {sorted(desconhecidos)}"
            )

        itens.append(
            Manifestacao(
                texto=registro["texto"],
                rotulos=list(rotulos),
                id=registro.get("id"),
            )
        )
    return itens


def particionar(
    itens: list[Manifestacao],
    fracao_validacao: float = 0.15,
    fracao_teste: float = 0.15,
    semente: int = 13460,
) -> Particoes:
    """Divide o corpus estratificando pela classe primária.

    A estratificação importa aqui porque `denuncia` e `elogio` são raras: uma
    divisão aleatória simples pode deixar o teste com pouquíssimas denúncias e
    tornar o F1 dessa classe puro ruído amostral.

    Args:
        itens: corpus completo.
        fracao_validacao: proporção destinada à validação.
        fracao_teste: proporção destinada ao teste.
        semente: semente do embaralhamento, para reprodutibilidade.

    Returns:
        As três partições.
    """
    if fracao_validacao + fracao_teste >= 1.0:
        raise ValueError("as frações de validação e teste somam 1.0 ou mais")

    rng = random.Random(semente)
    particoes = Particoes()

    por_classe: dict[str, list[Manifestacao]] = {r: [] for r in ROTULOS}
    for item in itens:
        por_classe[item.primaria].append(item)

    for grupo in por_classe.values():
        rng.shuffle(grupo)
        n_val = round(len(grupo) * fracao_validacao)
        n_teste = round(len(grupo) * fracao_teste)
        particoes.validacao.extend(grupo[:n_val])
        particoes.teste.extend(grupo[n_val : n_val + n_teste])
        particoes.treino.extend(grupo[n_val + n_teste :])

    for lista in (particoes.treino, particoes.validacao, particoes.teste):
        rng.shuffle(lista)
    return particoes


def truncar_cabeca_cauda(texto: str, tokenizer, max_tokens: int = 512) -> str:
    """Trunca preservando início e fim do texto, em vez de só o início.

    Manifestações longas trazem contexto no começo e o pedido concreto no fim;
    o truncamento padrão descartaria justamente a parte que decide o rótulo.

    Args:
        texto: texto original.
        tokenizer: tokenizer do modelo, usado para contar tokens.
        max_tokens: orçamento total, incluindo os dois tokens especiais.

    Returns:
        O texto original, se couber, ou a junção de sua cabeça e cauda.
    """
    ids = tokenizer.encode(texto, add_special_tokens=False)
    util = max_tokens - 2
    if len(ids) <= util:
        return texto
    cabeca = util // 4
    cauda = util - cabeca
    return tokenizer.decode(ids[:cabeca]) + " [...] " + tokenizer.decode(ids[-cauda:])
