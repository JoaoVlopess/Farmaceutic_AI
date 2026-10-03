import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings


MODELO_EMBEDDING = "gemini-embedding-001"
DIRETORIO_BANCO = "db/chroma"
NOME_COLECAO = "bulas_medicas"


def criar_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Cria o modelo de embeddings usado pelo banco vetorial."""
    load_dotenv()

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError(
            "A variável GEMINI_API_KEY não foi encontrada no arquivo .env"
        )

    return GoogleGenerativeAIEmbeddings(model=MODELO_EMBEDDING)


def obter_banco_vetorial() -> Chroma:
    """Abre ou cria a coleção persistente do Chroma."""
    return Chroma(
        persist_directory=DIRETORIO_BANCO,
        embedding_function=criar_embeddings(),
        collection_name=NOME_COLECAO,
    )
