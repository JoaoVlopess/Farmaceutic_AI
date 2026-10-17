"""Gera um relatório dos PDFs indexados e ainda pendentes."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from RAG.banco_vetorial import obter_banco_vetorial


@dataclass(frozen=True)
class LinhaRelatorio:
    status: str
    arquivo: str
    medicamento: str
    forma_farmaceutica: str
    chunks_armazenados: int


def gerar_relatorio(pasta_bulas: str | Path = "bulas_pdf") -> list[LinhaRelatorio]:
    pasta = Path(pasta_bulas)
    pendentes = {
        caminho.name
        for caminho in pasta.glob("*.pdf")
        if caminho.is_file()
    }

    banco = obter_banco_vetorial()
    resultado = banco.get(include=["metadatas"])
    agrupados: dict[tuple[str, str, str], int] = defaultdict(int)

    for metadata in resultado.get("metadatas", []):
        if not metadata:
            continue
        fonte = str(metadata.get("source", "fonte-nao-informada"))
        arquivo = str(metadata.get("arquivo_nome") or Path(fonte).name)
        medicamento = str(metadata.get("medicamento", "não identificado"))
        forma = str(metadata.get("forma_farmaceutica", "não identificada"))
        agrupados[(arquivo, medicamento, forma)] += 1

    linhas: list[LinhaRelatorio] = []
    arquivos_encontrados: set[str] = set()
    for (arquivo, medicamento, forma), chunks in agrupados.items():
        arquivos_encontrados.add(arquivo)
        status = "PENDENTE/INCOMPLETO" if arquivo in pendentes else "INDEXADO"
        linhas.append(
            LinhaRelatorio(
                status=status,
                arquivo=arquivo,
                medicamento=medicamento,
                forma_farmaceutica=forma,
                chunks_armazenados=chunks,
            )
        )

    for arquivo in pendentes - arquivos_encontrados:
        linhas.append(
            LinhaRelatorio(
                status="PENDENTE",
                arquivo=arquivo,
                medicamento="—",
                forma_farmaceutica="—",
                chunks_armazenados=0,
            )
        )

    return sorted(
        linhas,
        key=lambda linha: (linha.status != "INDEXADO", linha.arquivo.casefold()),
    )


def salvar_csv(
    linhas: list[LinhaRelatorio],
    destino: str | Path = "relatorio_medicamentos.csv",
) -> Path:
    caminho = Path(destino)
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(
            [
                "status",
                "arquivo",
                "medicamento",
                "forma_farmaceutica",
                "chunks_armazenados",
            ]
        )
        for linha in linhas:
            escritor.writerow(
                [
                    linha.status,
                    linha.arquivo,
                    linha.medicamento,
                    linha.forma_farmaceutica,
                    linha.chunks_armazenados,
                ]
            )
    return caminho


def main() -> None:
    linhas = gerar_relatorio()
    caminho_csv = salvar_csv(linhas)

    indexados = {linha.arquivo for linha in linhas if linha.status == "INDEXADO"}
    pendentes = {linha.arquivo for linha in linhas if linha.status != "INDEXADO"}
    total_chunks = sum(linha.chunks_armazenados for linha in linhas)

    print(f"Arquivos indexados e confirmados: {len(indexados)}")
    print(f"Arquivos pendentes ou incompletos: {len(pendentes)}")
    print(f"Chunks atualmente armazenados: {total_chunks}")
    print(f"Relatório salvo em: {caminho_csv.resolve()}")
    print("\nSTATUS | ARQUIVO | MEDICAMENTO | FORMA | CHUNKS")
    for linha in linhas:
        print(
            f"{linha.status} | {linha.arquivo} | {linha.medicamento} | "
            f"{linha.forma_farmaceutica} | {linha.chunks_armazenados}"
        )


if __name__ == "__main__":
    main()
