"""Exemplo de consulta ao RAG já indexado."""

from models import SolicitacaoInformacao
from services import gerar_informacao


def main() -> None:
    solicitacao = SolicitacaoInformacao(
        medicamento="Dorflex",
        forma_farmaceutica="comprimido",
        pergunta="Quais são as indicações de uso desse medicamento?",
    )

    resposta, chunks = gerar_informacao(solicitacao)
    print("=== RESPOSTA ===")
    print(resposta.model_dump_json(indent=2))
    print(f"\n=== CHUNKS UTILIZADOS ({len(chunks)}) ===")
    for numero, chunk in enumerate(chunks, start=1):
        print(f"\n--- Chunk {numero} ---")
        print(f"Seção: {chunk.metadata.get('section_title', 'Não informada')}")
        print(f"Fonte: {chunk.metadata.get('source', 'Não informada')}")
        print(chunk.page_content)


if __name__ == "__main__":
    main()
