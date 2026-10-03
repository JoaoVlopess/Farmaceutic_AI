import re
from hashlib import sha256

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from RAG.banco_vetorial import obter_banco_vetorial
from tools import extrair_paginas_pdf
from utils import (
    eh_inicio_conteudo_bula,
    filtrar_paginas_bula,
    identificar_forma_farmaceutica,
    identificar_nome_medicamento,
    normalizar_nome_medicamento,
)


def criar_documentos(caminho_arquivo: str) -> list[Document]:
    """
    Cria um Document para cada bula/apresentação encontrada no PDF.

    Um PDF do Bulário pode reunir mais de uma bula. Separá-las antes do
    chunking impede que seções de medicamentos ou apresentações diferentes
    recebam os mesmos metadados.
    """
    paginas = filtrar_paginas_bula(extrair_paginas_pdf(caminho_arquivo))
    grupos_de_paginas: list[list[str]] = []
    grupo_atual: list[str] = []
    grupo_ja_tem_inicio = False

    for pagina in paginas:
        pagina_inicia_bula = eh_inicio_conteudo_bula(pagina)

        if pagina_inicia_bula and grupo_ja_tem_inicio:
            grupos_de_paginas.append(grupo_atual)
            grupo_atual = []

        grupo_atual.append(pagina)
        if pagina_inicia_bula:
            grupo_ja_tem_inicio = True

    if grupo_atual:
        grupos_de_paginas.append(grupo_atual)

    documentos: list[Document] = []
    for indice, paginas_da_bula in enumerate(grupos_de_paginas, start=1):
        texto = "\n\n".join(paginas_da_bula)
        medicamento = identificar_nome_medicamento(texto)
        forma_farmaceutica = identificar_forma_farmaceutica(texto)
        documentos.append(
            Document(
                page_content=texto,
                metadata={
                    "source": caminho_arquivo,
                    "bula_index": indice,
                    "medicamento": medicamento,
                    "medicamento_normalizado": normalizar_nome_medicamento(medicamento),
                    "forma_farmaceutica": forma_farmaceutica,
                },
            )
        )

    return documentos


def criar_documento(caminho_arquivo: str) -> Document:
    """Cria um documento quando o PDF contém exatamente uma bula."""
    documentos = criar_documentos(caminho_arquivo)
    if len(documentos) != 1:
        raise ValueError(
            f"O PDF contém {len(documentos)} bulas. Use criar_documentos()."
        )
    return documentos[0]



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

    chunks_finais: list[Document] = []

    for secao in secoes:

        secao = secao.strip()

        if not secao:
            continue

        # Pega número e título da seção
        match = re.match(
            r'^(\d+)\.\s+([^\n]+)',
            secao
        )

        if match:
            numero_secao = int(match.group(1))
            titulo_secao = match.group(2).strip()
            conteudo = secao[match.end():].strip()
        else:
            # Preserva nome, apresentações e composição, que aparecem antes
            # da primeira seção numerada e também são relevantes para o RAG.
            numero_secao = 0
            titulo_secao = "APRESENTAÇÕES E COMPOSIÇÃO"
            conteudo = secao

        # Para cada sessão aplica o splitter
        sub_chunks = splitter.create_documents([conteudo])

        for indice, sub_chunk in enumerate(sub_chunks, start=1):

            chunk_id = f"{documento.metadata['bula_index']}.{numero_secao}.{indice}"
            medicamento = documento.metadata["medicamento"]

            texto_chunk = (
                f"Medicamento: {medicamento}\n"
                f"Forma farmacêutica: {documento.metadata['forma_farmaceutica']}\n"
                f"{numero_secao}. {titulo_secao}\n\n"
                f"{sub_chunk.page_content}"
            )

            id_documento = sha256(
                (
                    f"{documento.metadata['source']}|"
                    f"{chunk_id}"
                ).encode("utf-8")
            ).hexdigest()

            chunks_finais.append(
                Document(
                    id=id_documento,
                    page_content=texto_chunk,
                    metadata={
                        **documento.metadata,
                        "chunk_id": chunk_id,
                        "section_number": numero_secao,
                        "section_title": titulo_secao
                    }
                )
            )

    return chunks_finais

def indexar_chunks(chunks: list[Document]) -> None:
    """Adiciona os chunks à coleção configurada no banco vetorial."""
    if not chunks:
        return
    banco = obter_banco_vetorial()
    banco.add_documents(chunks, ids=[chunk.id for chunk in chunks])

caminhos_pdf = [
    "bulas_pdf/bula_1791032447500.pdf",
    "bulas_pdf/bula_1791037184119.pdf"
]

def main():
    total_chunks = 0
    for caminho in caminhos_pdf:
        for documento in criar_documentos(caminho):
            chunks = dividir_bula(documento)
            indexar_chunks(chunks)
            total_chunks += len(chunks)
            print(
                f"{documento.metadata['medicamento']}: "
                f"{documento.metadata['forma_farmaceutica']}, "
                f"{len(chunks)} chunks indexados."
            )

    print(f"Indexação concluída: {total_chunks} chunks no total.")


if __name__ == "__main__":
    main()
