"""Fine-tuning de um encoder para triagem de manifestações de ouvidoria.

O modelo é multirrótulo (sigmoide por classe, não softmax), porque uma
manifestação real costuma carregar mais de uma intenção. A classe primária é
derivada depois, por precedência, em `taxonomia.classe_primaria`.

Uso:
    python src/treino.py --config configs/base.yaml
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
import torch
import yaml
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from avaliacao import avaliar
from dados import Manifestacao, carregar_jsonl, particionar, truncar_cabeca_cauda
from taxonomia import ID2ROTULO, PESO_CLASSE, ROTULOS, ROTULO2ID, classe_primaria


class CorpusManifestacoes(Dataset):
    """Adapta as manifestações anotadas ao formato esperado pelo Trainer."""

    def __init__(self, itens: list[Manifestacao], tokenizer, max_tokens: int):
        self.itens = itens
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens

    def __len__(self) -> int:
        return len(self.itens)

    def __getitem__(self, indice: int) -> dict:
        item = self.itens[indice]
        texto = truncar_cabeca_cauda(item.texto, self.tokenizer, self.max_tokens)
        codificado = self.tokenizer(
            texto,
            truncation=True,
            max_length=self.max_tokens,
            padding="max_length",
        )
        codificado["labels"] = item.vetor_multirrotulo()
        return {chave: torch.tensor(valor) for chave, valor in codificado.items()}


class TreinadorPonderado(Trainer):
    """Trainer com BCE ponderada por classe.

    O peso vem de `taxonomia.PESO_CLASSE` e embute a assimetria de custo:
    perder uma denúncia é muito mais caro que gerar triagem extra.
    """

    def __init__(self, *args, pesos: torch.Tensor, **kwargs):
        super().__init__(*args, **kwargs)
        self.pesos = pesos

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        alvos = inputs.pop("labels")
        saidas = model(**inputs)
        perda = torch.nn.functional.binary_cross_entropy_with_logits(
            saidas.logits,
            alvos.to(saidas.logits.dtype),
            pos_weight=self.pesos.to(saidas.logits.device),
        )
        return (perda, saidas) if return_outputs else perda


def _metricas(predicao) -> dict:
    """Converte as saídas do Trainer nas métricas de triagem.

    Args:
        predicao: objeto EvalPrediction com logits e alvos multirrótulo.

    Returns:
        macro-F1 e vazamento de denúncia, para seleção do melhor checkpoint.
    """
    logits, alvos = predicao.predictions, predicao.label_ids
    probabilidades = 1 / (1 + np.exp(-logits))

    previstos, verdadeiros = [], []
    for linha_prob, linha_alvo in zip(probabilidades, alvos):
        ativos = [ID2ROTULO[i] for i, p in enumerate(linha_prob) if p >= 0.5]
        previstos.append(
            classe_primaria(ativos) if ativos else ID2ROTULO[int(linha_prob.argmax())]
        )
        verdadeiros.append(
            classe_primaria([ID2ROTULO[i] for i, a in enumerate(linha_alvo) if a > 0.5])
        )

    resultado = avaliar(verdadeiros, previstos)
    return {
        "macro_f1": resultado.macro_f1,
        "vazamento_denuncia": resultado.vazamento_denuncia,
        **{f"f1_{r}": v for r, v in resultado.f1_por_classe.items()},
    }


def treinar(config: dict) -> None:
    """Executa o fine-tuning completo e grava o checkpoint e o relatório.

    Args:
        config: dicionário carregado do YAML de configuração.
    """
    tokenizer = AutoTokenizer.from_pretrained(config["modelo_base"])
    modelo = AutoModelForSequenceClassification.from_pretrained(
        config["modelo_base"],
        num_labels=len(ROTULOS),
        problem_type="multi_label_classification",
        id2label=dict(ID2ROTULO),
        label2id=dict(ROTULO2ID),
    )

    itens = carregar_jsonl(config["corpus"])
    particoes = particionar(
        itens,
        fracao_validacao=config["fracao_validacao"],
        fracao_teste=config["fracao_teste"],
        semente=config["semente"],
    )
    print(
        f"corpus: {len(itens)} manifestações — "
        f"treino {len(particoes.treino)} / "
        f"validação {len(particoes.validacao)} / "
        f"teste {len(particoes.teste)}"
    )

    max_tokens = config["max_tokens"]
    pesos = torch.tensor([PESO_CLASSE[r] for r in ROTULOS])

    argumentos = TrainingArguments(
        output_dir=config["saida"],
        num_train_epochs=config["epocas"],
        learning_rate=float(config["learning_rate"]),
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        warmup_ratio=config["warmup_ratio"],
        weight_decay=config["weight_decay"],
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_steps=25,
        bf16=torch.cuda.is_available(),
        report_to=[],
        seed=config["semente"],
    )

    treinador = TreinadorPonderado(
        model=modelo,
        args=argumentos,
        train_dataset=CorpusManifestacoes(particoes.treino, tokenizer, max_tokens),
        eval_dataset=CorpusManifestacoes(particoes.validacao, tokenizer, max_tokens),
        compute_metrics=_metricas,
        pesos=pesos,
    )
    treinador.train()

    saida = pathlib.Path(config["saida"])
    treinador.save_model(str(saida / "melhor"))
    tokenizer.save_pretrained(str(saida / "melhor"))

    print("\n=== teste (conjunto nunca visto) ===")
    metricas_teste = treinador.evaluate(
        CorpusManifestacoes(particoes.teste, tokenizer, max_tokens),
        metric_key_prefix="teste",
    )
    for chave, valor in metricas_teste.items():
        print(f"{chave}: {valor}")
    (saida / "metricas_teste.json").write_text(
        json.dumps(metricas_teste, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main() -> None:
    """Lê a configuração da linha de comando e dispara o treino."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/base.yaml")
    argumentos = parser.parse_args()

    config = yaml.safe_load(pathlib.Path(argumentos.config).read_text(encoding="utf-8"))
    treinar(config)


if __name__ == "__main__":
    main()
