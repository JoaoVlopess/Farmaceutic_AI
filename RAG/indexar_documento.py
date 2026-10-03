import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from tools.tratamento_pdf import extrair_texto_pdf
from RAG.banco_vetorial import obter_banco_vetorial

def criar_documento(caminho_arquivo: str) -> Document:
    """
    Cria um objeto Document a partir de um arquivo PDF.

    Args:
        caminho_arquivo (str): O caminho para o arquivo PDF.

    Returns:
        Document: Um objeto Document contendo o conteúdo do PDF.
    """
    texto = extrair_texto_pdf(caminho_arquivo, limpar=True)
    return Document(page_content=texto, metadata={"source": caminho_arquivo})



def dividir_bula(
    documento: Document,
    max_tokens: int = 500,
    overlap_tokens: int = 50
) -> list[Document]:

    texto = documento.page_content.strip()

    # 1. Separa sempre que encontrar:
    # 1. ALGUM TÍTULO
    # 2. ALGUM TÍTULO
    # 3. ALGUM TÍTULO...
    secoes = re.split(
        r'(?m)(?=^\s*\d+\.\s+)',
        texto
    )

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=max_tokens,
        chunk_overlap=overlap_tokens,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            " ",
            ""
        ]
    )

    chunks_finais = []

    for secao in secoes:

        secao = secao.strip()

        if not secao:
            continue

        # Pega número e título da seção
        match = re.match(
            r'^(\d+)\.\s+([^\n]+)',
            secao
        )

        if not match:
            continue

        numero_secao = match.group(1)
        titulo_secao = match.group(2).strip()

        # Retira o título para dividir apenas o conteúdo
        conteudo = secao[match.end():].strip()

        # Para cada sessão aplica o splitter
        sub_chunks = splitter.create_documents([conteudo])

        for indice, sub_chunk in enumerate(sub_chunks, start=1):

            chunk_id = f"{numero_secao}.{indice}"

            texto_chunk = (
                f"{numero_secao}. {titulo_secao}\n\n"
                f"{sub_chunk.page_content}"
            )

            chunks_finais.append(
                Document(
                    page_content=texto_chunk,
                    metadata={
                        **documento.metadata,
                        "chunk_id": chunk_id,
                        "section_number": int(numero_secao),
                        "section_title": titulo_secao
                    }
                )
            )

    return chunks_finais

def indexar_chunks(chunks: list[Document]) -> None:
    """Adiciona os chunks à coleção configurada no banco vetorial."""
    banco = obter_banco_vetorial()
    banco.add_documents(chunks)

caminhos_pdf = [
    "bulas_pdf/bula_1791032447500.pdf",
    "bulas_pdf/bula_1791037184119.pdf"
]

def main():
    for caminho in caminhos_pdf:
        documento = criar_documento(caminho)
        chunks = dividir_bula(documento)
        indexar_chunks(chunks)

    print(f"Indexação concluída: {len(chunks)} chunks.")


if __name__ == "__main__":
    main()
