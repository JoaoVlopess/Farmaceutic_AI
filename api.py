"""API HTTP que conecta o frontend Angular ao RAG de bulas."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langchain_core.documents import Document
from pydantic import BaseModel

from models import SolicitacaoInformacao
from RAG import listar_catalogo_medicamentos, obter_banco_vetorial
from services import gerar_informacao


PASTA_BULAS_ARQUIVADAS = Path("bulas_processadas")


class ApresentacaoCatalogo(BaseModel):
    id: str
    forma: str
    concentracao: str
    via_administracao: str
    tipo_bula: str


class MedicamentoCatalogo(BaseModel):
    id: str
    nome: str
    nome_comercial: str
    principio_ativo: str
    aliases: list[str]
    numero_registro: str
    fabricante: str
    apresentacoes: list[ApresentacaoCatalogo]


class FonteBula(BaseModel):
    indice: int
    medicamento: str | None
    principio_ativo: str | None
    forma_farmaceutica: str | None
    concentracao: str | None
    secao_numero: int | None
    secao_titulo: str | None
    pagina: int | None
    pagina_final: int | None
    arquivo: str
    arquivo_hash: str | None
    chunk_id: str | None
    numero_registro: str | None
    versao_bula: str | None
    data_bula: str | None
    fonte_nome: str
    fonte_url: str | None
    trecho: str


class RespostaConsulta(BaseModel):
    resposta: str
    fontes: list[FonteBula]


app = FastAPI(
    title="Farmaceutic AI API",
    description="Consulta semântica às bulas indexadas no Chroma.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _texto_ou_none(valor: object) -> str | None:
    texto = str(valor).strip() if valor is not None else ""
    return texto or None


def _url_fonte(metadata: dict) -> str | None:
    oficial = _texto_ou_none(metadata.get("fonte_url"))
    if oficial:
        return oficial
    arquivo_id = _texto_ou_none(
        metadata.get("arquivo_hash_sha256") or metadata.get("arquivo_id")
    )
    arquivado = _texto_ou_none(metadata.get("arquivo_arquivado_nome"))
    if arquivo_id and arquivado and (PASTA_BULAS_ARQUIVADAS / arquivado).is_file():
        return f"/api/fontes/{arquivo_id}"
    return None


def _serializar_fonte(documento: Document, indice: int) -> FonteBula:
    metadata = documento.metadata
    arquivo = str(metadata.get("arquivo_nome", "")).strip()
    if not arquivo:
        arquivo = Path(str(metadata.get("source", "Fonte não informada"))).name
    numero_secao = metadata.get("section_number")
    pagina = metadata.get("pagina_pdf")
    pagina_final = metadata.get("pagina_pdf_final")

    return FonteBula(
        indice=indice,
        medicamento=_texto_ou_none(
            metadata.get("nome_comercial") or metadata.get("medicamento")
        ),
        principio_ativo=_texto_ou_none(metadata.get("principio_ativo")),
        forma_farmaceutica=_texto_ou_none(metadata.get("forma_farmaceutica")),
        concentracao=_texto_ou_none(metadata.get("concentracao")),
        secao_numero=int(numero_secao) if numero_secao is not None else None,
        secao_titulo=_texto_ou_none(metadata.get("section_title")),
        pagina=int(pagina) if pagina is not None else None,
        pagina_final=int(pagina_final) if pagina_final is not None else None,
        arquivo=arquivo,
        arquivo_hash=_texto_ou_none(
            metadata.get("arquivo_hash_sha256") or metadata.get("arquivo_id")
        ),
        chunk_id=_texto_ou_none(metadata.get("chunk_id")),
        numero_registro=_texto_ou_none(metadata.get("numero_registro")),
        versao_bula=_texto_ou_none(metadata.get("versao_bula")),
        data_bula=_texto_ou_none(metadata.get("data_bula")),
        fonte_nome=str(metadata.get("fonte_oficial", "Bula indexada")),
        fonte_url=_url_fonte(metadata),
        trecho=documento.page_content,
    )


def _eh_erro_de_cota(erro: Exception) -> bool:
    mensagem = str(erro).casefold()
    return "resource_exhausted" in mensagem or "quota" in mensagem or "429" in mensagem


@app.get("/api/saude")
def verificar_saude() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/medicamentos", response_model=list[MedicamentoCatalogo])
def obter_medicamentos() -> list[MedicamentoCatalogo]:
    try:
        return [MedicamentoCatalogo(**item) for item in listar_catalogo_medicamentos()]
    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível carregar os medicamentos indexados.",
        ) from erro


@app.get("/api/fontes/{arquivo_id}")
def abrir_fonte(arquivo_id: str) -> FileResponse:
    """Abre somente PDFs que foram arquivados e confirmados no Chroma."""
    if len(arquivo_id) != 64 or any(char not in "0123456789abcdef" for char in arquivo_id):
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    banco = obter_banco_vetorial()
    resultado = banco.get(where={"arquivo_id": arquivo_id}, include=["metadatas"])
    if not resultado.get("metadatas"):
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    metadata = resultado["metadatas"][0]
    nome_arquivado = str(metadata.get("arquivo_arquivado_nome", ""))
    caminho = (PASTA_BULAS_ARQUIVADAS / nome_arquivado).resolve()
    pasta = PASTA_BULAS_ARQUIVADAS.resolve()
    if not nome_arquivado or not caminho.is_relative_to(pasta) or not caminho.is_file():
        raise HTTPException(status_code=404, detail="PDF original não está disponível.")
    return FileResponse(
        caminho,
        media_type="application/pdf",
        filename=str(metadata.get("arquivo_nome", nome_arquivado)),
    )


@app.post("/api/consultas", response_model=RespostaConsulta)
def consultar_bula(solicitacao: SolicitacaoInformacao) -> RespostaConsulta:
    """Embute a pergunta, busca os chunks e gera a resposta fundamentada."""
    try:
        resposta, documentos = gerar_informacao(solicitacao)
    except Exception as erro:
        if _eh_erro_de_cota(erro):
            raise HTTPException(
                status_code=429,
                detail=(
                    "A cota de embeddings do Gemini está temporariamente "
                    "esgotada. Tente novamente após a renovação da cota."
                ),
            ) from erro
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o modelo neste momento.",
        ) from erro

    return RespostaConsulta(
        resposta=resposta.explicacao,
        fontes=[
            _serializar_fonte(documento, indice)
            for indice, documento in enumerate(documentos, start=1)
        ],
    )
