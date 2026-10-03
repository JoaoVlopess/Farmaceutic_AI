from langchain_core.documents import Document

from RAG.banco_vetorial import obter_banco_vetorial
from utils import normalizar_nome_medicamento


def listar_medicamentos() -> list[str]:
    """Lista os medicamentos disponíveis nos metadados da coleção."""
    banco = obter_banco_vetorial()
    resultado = banco.get(include=["metadatas"])
    medicamentos = {
        metadata["medicamento"]
        for metadata in resultado.get("metadatas", [])
        if metadata and metadata.get("medicamento")
    }
    return sorted(medicamentos, key=str.casefold)


def listar_formas_farmaceuticas(medicamento: str) -> list[str]:
    """Lista as formas disponíveis para o medicamento selecionado."""
    banco = obter_banco_vetorial()
    resultado = banco.get(
        where={
            "medicamento_normalizado": normalizar_nome_medicamento(medicamento)
        },
        include=["metadatas"],
    )
    formas = {
        metadata["forma_farmaceutica"]
        for metadata in resultado.get("metadatas", [])
        if metadata and metadata.get("forma_farmaceutica")
    }
    return sorted(formas, key=str.casefold)


def buscar_bula(
    pergunta: str,
    medicamento: str,
    forma_farmaceutica: str | None = None,
    quantidade: int = 3,
) -> list[Document]:
    """Busca chunks semanticamente relevantes somente do medicamento escolhido."""
    banco = obter_banco_vetorial()

    filtro_medicamento = {
        "medicamento_normalizado": normalizar_nome_medicamento(medicamento)
    }
    filtro = filtro_medicamento
    if forma_farmaceutica:
        filtro = {
            "$and": [
                filtro_medicamento,
                {"forma_farmaceutica": forma_farmaceutica.casefold().strip()},
            ]
        }

    documentos = banco.similarity_search(
        query=pergunta,
        k=quantidade,
        filter=filtro,
    )

    return documentos


def main() -> None:
    medicamento = "Dorflex"
    forma_farmaceutica = "comprimido"
    pergunta = "Qual a periodicidade que eu devo tomar dorflex?"
    documentos = buscar_bula(pergunta, medicamento, forma_farmaceutica)

    print(f"Medicamentos disponíveis: {', '.join(listar_medicamentos())}")
    print(
        "Formas disponíveis: "
        f"{', '.join(listar_formas_farmaceuticas(medicamento))}"
    )
    print(f"Medicamento selecionado: {medicamento}")
    print(f"Forma farmacêutica: {forma_farmaceutica}")
    print(f"Pergunta: {pergunta}")
    print(f"Documentos encontrados: {len(documentos)}")

    for numero, documento in enumerate(documentos, start=1):
        print(f"\n--- Resultado {numero} ---")
        print(f"Medicamento: {documento.metadata.get('medicamento')}")
        print(f"Fonte: {documento.metadata.get('source', 'Fonte não informada')}")
        print(documento.page_content)


if __name__ == "__main__":
    main()
