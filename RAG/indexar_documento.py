import re
import time
from collections import Counter, deque
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from RAG.banco_vetorial import obter_banco_vetorial
from tools import extrair_paginas_pdf
from utils import (
    construir_metadados_bula,
    eh_inicio_conteudo_bula,
    filtrar_paginas_bula_numeradas,
)


# A cota gratuita observada para embeddings é de 100 entradas/minuto. Usamos
# 60 para reservar capacidade para buscas simultâneas e pequenas diferenças
# entre a janela local e a janela contabilizada pelo servidor.
LIMITE_EMBEDDINGS_POR_MINUTO = 60
TAMANHO_LOTE_EMBEDDINGS = 30
_janela_embeddings: deque[tuple[float, int]] = deque()


@dataclass(frozen=True)
class ResultadoIndexacao:
    """Resumo de um PDF confirmado no banco vetorial."""

    arquivo: Path
    medicamentos: tuple[str, ...]
    quantidade_bulas: int
    quantidade_chunks: int
    ids: tuple[str, ...]


def _sha256_arquivo(caminho: Path) -> str:
    digest = sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def criar_documentos(caminho_arquivo: str | Path) -> list[Document]:
    """
    Cria um Document para cada bula/apresentação encontrada no PDF.

    Um PDF do Bulário pode reunir mais de uma bula. Separá-las antes do
    chunking impede que seções de medicamentos ou apresentações diferentes
    recebam os mesmos metadados.
    """
    caminho = Path(caminho_arquivo)
    arquivo_id = _sha256_arquivo(caminho)
    fonte = caminho.as_posix()
    paginas = filtrar_paginas_bula_numeradas(extrair_paginas_pdf(caminho))
    grupos_de_paginas: list[list[tuple[int, str]]] = []
    grupo_atual: list[tuple[int, str]] = []
    grupo_ja_tem_inicio = False

    for numero_pagina, pagina in paginas:
        pagina_inicia_bula = eh_inicio_conteudo_bula(pagina)

        if pagina_inicia_bula and grupo_ja_tem_inicio:
            grupos_de_paginas.append(grupo_atual)
            grupo_atual = []

        grupo_atual.append((numero_pagina, pagina))
        if pagina_inicia_bula:
            grupo_ja_tem_inicio = True

    if grupo_atual:
        grupos_de_paginas.append(grupo_atual)

    documentos: list[Document] = []
    for indice, paginas_da_bula in enumerate(grupos_de_paginas, start=1):
        texto_limpo = "\n\n".join(texto for _, texto in paginas_da_bula)
        texto_marcado = "\n\n".join(
            f"<<<PAGINA_PDF:{numero}>>>\n{texto}"
            for numero, texto in paginas_da_bula
        )
        metadados = construir_metadados_bula(
            texto_limpo,
            caminho,
            arquivo_id,
            indice,
        )
        documentos.append(
            Document(
                page_content=texto_marcado,
                metadata={
                    **metadados,
                    "source": fonte,
                    "pagina_inicial": paginas_da_bula[0][0],
                    "pagina_final": paginas_da_bula[-1][0],
                },
            )
        )

    return documentos


def criar_documento(caminho_arquivo: str | Path) -> Document:
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
    overlap_tokens: int = 50,
) -> list[Document]:
    """Divide por seção e mantém a página física de cada trecho."""
    pagina_re = re.compile(r"(?m)^<<<PAGINA_PDF:(\d+)>>>\s*\n?")
    marcadores = list(pagina_re.finditer(documento.page_content))
    if not marcadores:
        return _dividir_bula_legado(documento, max_tokens, overlap_tokens)

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=max_tokens,
        chunk_overlap=overlap_tokens,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
    )
    paginas: list[tuple[int, str]] = []
    for posicao, marcador in enumerate(marcadores):
        inicio = marcador.end()
        fim = marcadores[posicao + 1].start() if posicao + 1 < len(marcadores) else None
        paginas.append((int(marcador.group(1)), documento.page_content[inicio:fim].strip()))

    chunks_finais: list[Document] = []
    ocorrencias_por_secao: Counter[int] = Counter()
    contador_subchunks: Counter[tuple[int, int, int]] = Counter()
    secao_ativa: tuple[int, str, int] | None = None

    for pagina_pdf, texto_pagina in paginas:
        secoes = re.split(r"(?m)(?=^\s*\d+\.\s+)", texto_pagina)
        for secao in secoes:
            secao = secao.strip()
            if not secao:
                continue

            match = re.match(r"^(\d+)\.\s+([^\n]+)", secao)
            if match:
                numero_secao = int(match.group(1))
                titulo_secao = match.group(2).strip()
                conteudo = secao[match.end():].strip()
                ocorrencias_por_secao[numero_secao] += 1
                ocorrencia_secao = ocorrencias_por_secao[numero_secao]
                secao_ativa = (numero_secao, titulo_secao, ocorrencia_secao)
            elif secao_ativa:
                numero_secao, titulo_secao, ocorrencia_secao = secao_ativa
                conteudo = secao
            else:
                numero_secao = 0
                titulo_secao = "APRESENTAÇÕES E COMPOSIÇÃO"
                conteudo = secao
                ocorrencias_por_secao[0] += 1
                ocorrencia_secao = ocorrencias_por_secao[0]
                secao_ativa = (numero_secao, titulo_secao, ocorrencia_secao)

            for sub_chunk in splitter.create_documents([conteudo]):
                chave = (pagina_pdf, numero_secao, ocorrencia_secao)
                contador_subchunks[chave] += 1
                indice = contador_subchunks[chave]
                chunk_id = (
                    f"{documento.metadata['bula_index']}.p{pagina_pdf}."
                    f"{numero_secao}.{ocorrencia_secao}.{indice}"
                )
                texto_chunk = (
                    f"Medicamento: {documento.metadata['medicamento']}\n"
                    f"Forma farmacêutica: {documento.metadata['forma_farmaceutica']}\n"
                    f"{numero_secao}. {titulo_secao}\n\n{sub_chunk.page_content}"
                )
                arquivo_id = documento.metadata.get("arquivo_id") or sha256(
                    str(documento.metadata["source"]).encode("utf-8")
                ).hexdigest()
                id_documento = sha256(
                    f"{arquivo_id}|{chunk_id}".encode("utf-8")
                ).hexdigest()
                chunks_finais.append(
                    Document(
                        id=id_documento,
                        page_content=texto_chunk,
                        metadata={
                            **documento.metadata,
                            "chunk_id": chunk_id,
                            "section_number": numero_secao,
                            "section_title": titulo_secao,
                            "pagina_pdf": pagina_pdf,
                            "pagina_pdf_final": pagina_pdf,
                        },
                    )
                )

    return chunks_finais


def _dividir_bula_legado(
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
    ocorrencias_por_secao: Counter[int] = Counter()

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

        ocorrencias_por_secao[numero_secao] += 1
        ocorrencia_secao = ocorrencias_por_secao[numero_secao]

        # Para cada sessão aplica o splitter
        sub_chunks = splitter.create_documents([conteudo])

        for indice, sub_chunk in enumerate(sub_chunks, start=1):

            chunk_id = (
                f"{documento.metadata['bula_index']}."
                f"{numero_secao}.{ocorrencia_secao}.{indice}"
            )
            medicamento = documento.metadata["medicamento"]

            texto_chunk = (
                f"Medicamento: {medicamento}\n"
                f"Forma farmacêutica: {documento.metadata['forma_farmaceutica']}\n"
                f"{numero_secao}. {titulo_secao}\n\n"
                f"{sub_chunk.page_content}"
            )

            arquivo_id = documento.metadata.get("arquivo_id") or sha256(
                str(documento.metadata["source"]).encode("utf-8")
            ).hexdigest()
            id_documento = sha256(
                (
                    f"{arquivo_id}|"
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


def _aguardar_cota_embeddings(quantidade: int) -> None:
    """Reserva espaço numa janela móvel local antes de chamar o Gemini."""
    if quantidade > LIMITE_EMBEDDINGS_POR_MINUTO:
        raise ValueError("O lote excede o limite local de embeddings por minuto.")

    while True:
        agora = time.monotonic()
        while _janela_embeddings and agora - _janela_embeddings[0][0] >= 60:
            _janela_embeddings.popleft()

        usados = sum(total for _, total in _janela_embeddings)
        if usados + quantidade <= LIMITE_EMBEDDINGS_POR_MINUTO:
            _janela_embeddings.append((agora, quantidade))
            return

        espera = max(0.1, 60 - (agora - _janela_embeddings[0][0]) + 0.5)
        print(
            f"[COTA] Aguardando {espera:.0f}s para respeitar "
            f"{LIMITE_EMBEDDINGS_POR_MINUTO} embeddings/minuto..."
        )
        time.sleep(espera)

def indexar_chunks(chunks: list[Document]) -> list[str]:
    """Grava, confirma e remove chunks obsoletos das mesmas fontes."""
    if not chunks:
        return []

    banco = obter_banco_vetorial()
    ids = [chunk.id for chunk in chunks]
    if any(chunk_id is None for chunk_id in ids):
        raise ValueError("Todos os chunks precisam ter um ID estável.")
    ids_esperados = [str(chunk_id) for chunk_id in ids]
    if len(ids_esperados) != len(set(ids_esperados)):
        repetidos = [
            chunk_id
            for chunk_id, quantidade in Counter(ids_esperados).items()
            if quantidade > 1
        ]
        raise ValueError(f"IDs de chunks duplicados: {', '.join(repetidos)}")

    fontes = {str(chunk.metadata["source"]) for chunk in chunks}
    ids_anteriores: set[str] = set()
    for fonte in fontes:
        existentes = banco.get(where={"source": fonte}, include=["metadatas"])
        ids_anteriores.update(existentes.get("ids", []))

    for inicio in range(0, len(chunks), TAMANHO_LOTE_EMBEDDINGS):
        lote_chunks = chunks[inicio : inicio + TAMANHO_LOTE_EMBEDDINGS]
        lote_ids = ids_esperados[inicio : inicio + TAMANHO_LOTE_EMBEDDINGS]
        _aguardar_cota_embeddings(len(lote_chunks))
        banco.add_documents(lote_chunks, ids=lote_ids)

    confirmacao = banco.get(ids=ids_esperados, include=["metadatas"])
    ids_confirmados = set(confirmacao.get("ids", []))
    ids_faltantes = set(ids_esperados) - ids_confirmados
    if ids_faltantes:
        raise RuntimeError(
            f"O Chroma não confirmou {len(ids_faltantes)} chunks; o PDF será mantido."
        )

    ids_obsoletos = ids_anteriores - set(ids_esperados)
    if ids_obsoletos:
        banco.delete(ids=sorted(ids_obsoletos))

    return ids_esperados


def indexar_pdf(caminho_arquivo: str | Path) -> ResultadoIndexacao:
    """Executa todo o pipeline de um PDF e só retorna após confirmar o Chroma."""
    caminho = Path(caminho_arquivo)
    documentos = criar_documentos(caminho)
    if not documentos:
        raise ValueError("Nenhuma bula válida foi encontrada no PDF.")

    chunks: list[Document] = []
    for documento in documentos:
        chunks.extend(dividir_bula(documento))
    if not chunks:
        raise ValueError("Nenhum chunk válido foi produzido para o PDF.")

    ids = indexar_chunks(chunks)
    medicamentos = tuple(
        dict.fromkeys(
            f"{documento.metadata['medicamento']} "
            f"({documento.metadata['forma_farmaceutica']})"
            for documento in documentos
        )
    )
    return ResultadoIndexacao(
        arquivo=caminho,
        medicamentos=medicamentos,
        quantidade_bulas=len(documentos),
        quantidade_chunks=len(chunks),
        ids=tuple(ids),
    )

def main():
    total_chunks = 0
    caminhos_pdf = sorted(Path("bulas_pdf").glob("*.pdf"))
    for caminho in caminhos_pdf:
        resultado = indexar_pdf(caminho)
        total_chunks += resultado.quantidade_chunks
        print(
            f"{', '.join(resultado.medicamentos)}: "
            f"{resultado.quantidade_chunks} chunks indexados."
        )

    print(f"Indexação concluída: {total_chunks} chunks no total.")


if __name__ == "__main__":
    main()
