"""Agente que responde exclusivamente a partir de chunks recuperados."""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI

from models import RespostaFarmaceutic, SolicitacaoInformacao
from prompts import PROMPT_CHAT_AGENT
from RAG import buscar_bula


load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    raise RuntimeError("A variável GEMINI_API_KEY não foi encontrada no arquivo .env")

modelo = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
agente_maestro = create_agent(
    model=modelo,
    system_prompt=PROMPT_CHAT_AGENT,
    response_format=ProviderStrategy(RespostaFarmaceutic),
)


def gerar_informacao(
    solicitacao: SolicitacaoInformacao,
) -> tuple[RespostaFarmaceutic, list[Document]]:
    """Gera a resposta e devolve os chunks numerados usados como contexto."""
    documentos = buscar_bula(
        pergunta=solicitacao.pergunta,
        medicamento=solicitacao.medicamento,
        forma_farmaceutica=solicitacao.forma_farmaceutica,
        quantidade=3,
        medicamento_id=solicitacao.medicamento_id,
        bula_id=solicitacao.bula_id,
    )

    if not documentos:
        return (
            RespostaFarmaceutic(
                explicacao=(
                    "Não encontrei conteúdo indexado para o medicamento e a "
                    "apresentação informados."
                )
            ),
            [],
        )

    mensagem = (
        f"Medicamento: {solicitacao.medicamento}\n"
        f"Forma farmacêutica: {solicitacao.forma_farmaceutica}\n"
        f"Pergunta: {solicitacao.pergunta}\n\n"
        "Fontes recuperadas da bula:\n"
    )
    for indice, documento in enumerate(documentos, start=1):
        mensagem += (
            f"\n[FONTE {indice}]\n"
            f"Seção: {documento.metadata.get('section_title', 'Não informada')}\n"
            f"Página: {documento.metadata.get('pagina_pdf', 'Não informada')}\n"
            f"Trecho:\n{documento.page_content}\n"
        )

    resultado = agente_maestro.invoke(
        {"messages": [{"role": "user", "content": mensagem}]}
    )
    return resultado["structured_response"], documentos
