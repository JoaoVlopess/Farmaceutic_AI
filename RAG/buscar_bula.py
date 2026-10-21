"""Catálogo e recuperação semântica das bulas indexadas."""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from RAG.banco_vetorial import obter_banco_vetorial
from utils import aliases_para_lista, normalizar_nome_medicamento


def listar_medicamentos() -> list[str]:
    """Lista os nomes de exibição disponíveis no catálogo profissional."""
    return [str(item["nome"]) for item in listar_catalogo_medicamentos()]


def listar_catalogo_medicamentos() -> list[dict[str, Any]]:
    """Agrupa produtos e apresentações usando IDs internos estáveis."""
    banco = obter_banco_vetorial()
    resultado = banco.get(include=["metadatas"])
    catalogo: dict[str, dict[str, Any]] = {}

    for metadata in resultado.get("metadatas", []):
        if not metadata:
            continue
        tipo_bula = str(metadata.get("tipo_bula", "profissional"))
        if tipo_bula == "paciente":
            continue

        nome = str(
            metadata.get("nome_comercial")
            or metadata.get("medicamento")
            or ""
        ).strip()
        if not nome:
            continue
        medicamento_id = str(
            metadata.get("medicamento_id")
            or f"legado:{normalizar_nome_medicamento(nome)}"
        )
        item = catalogo.setdefault(
            medicamento_id,
            {
                "id": medicamento_id,
                "nome": nome,
                "nome_comercial": nome,
                "principio_ativo": str(metadata.get("principio_ativo", "")),
                "aliases": set(),
                "numero_registro": str(metadata.get("numero_registro", "")),
                "fabricante": str(metadata.get("fabricante", "")),
                "apresentacoes": {},
            },
        )
        item["aliases"].update(aliases_para_lista(metadata.get("aliases_json")))
        item["aliases"].add(nome)
        if item["principio_ativo"]:
            item["aliases"].add(item["principio_ativo"])

        forma = str(metadata.get("forma_farmaceutica", "não identificada"))
        concentracao = str(metadata.get("concentracao", ""))
        via = str(metadata.get("via_administracao", ""))
        bula_id = str(
            metadata.get("bula_id")
            or f"{medicamento_id}:{normalizar_nome_medicamento(forma)}"
        )
        item["apresentacoes"][bula_id] = {
            "id": bula_id,
            "forma": forma,
            "concentracao": concentracao,
            "via_administracao": via,
            "tipo_bula": tipo_bula,
        }

    itens: list[dict[str, Any]] = []
    for item in catalogo.values():
        item["aliases"] = sorted(item["aliases"], key=str.casefold)
        item["apresentacoes"] = sorted(
            item["apresentacoes"].values(),
            key=lambda valor: (
                valor["forma"].casefold(),
                valor["concentracao"].casefold(),
            ),
        )
        itens.append(item)
    return sorted(itens, key=lambda item: item["nome"].casefold())


def listar_formas_farmaceuticas(medicamento: str) -> list[str]:
    """Lista as formas disponíveis para compatibilidade com clientes antigos."""
    chave = normalizar_nome_medicamento(medicamento)
    for item in listar_catalogo_medicamentos():
        pesquisaveis = [item["nome"], *item["aliases"]]
        if chave in {normalizar_nome_medicamento(valor) for valor in pesquisaveis}:
            return sorted(
                {apresentacao["forma"] for apresentacao in item["apresentacoes"]},
                key=str.casefold,
            )
    return []


def buscar_bula(
    pergunta: str,
    medicamento: str = "",
    forma_farmaceutica: str | None = None,
    quantidade: int = 3,
    medicamento_id: str | None = None,
    bula_id: str | None = None,
) -> list[Document]:
    """Faz o embedding da pergunta e restringe a busca à bula selecionada."""
    banco = obter_banco_vetorial()
    condicoes: list[dict[str, Any]] = []
    if bula_id:
        condicoes.append({"bula_id": bula_id})
    elif medicamento_id:
        condicoes.append({"medicamento_id": medicamento_id})
    elif medicamento:
        condicoes.append(
            {"medicamento_normalizado": normalizar_nome_medicamento(medicamento)}
        )
    else:
        raise ValueError("Informe medicamento_id, bula_id ou medicamento.")

    if forma_farmaceutica and not bula_id:
        condicoes.append(
            {"forma_farmaceutica": forma_farmaceutica.casefold().strip()}
        )
    if medicamento_id or bula_id:
        condicoes.append({"tipo_bula": "profissional"})

    filtro: dict[str, Any]
    if len(condicoes) == 1:
        filtro = condicoes[0]
    else:
        filtro = {"$and": condicoes}

    return banco.similarity_search(
        query=pergunta,
        k=quantidade,
        filter=filtro,
    )


def main() -> None:
    catalogo = listar_catalogo_medicamentos()
    print(f"Medicamentos profissionais disponíveis: {len(catalogo)}")
    for item in catalogo[:10]:
        print(f"- {item['nome']} [{item['id']}]")


if __name__ == "__main__":
    main()
