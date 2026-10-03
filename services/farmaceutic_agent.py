import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from RAG import buscar_bula
from models import SolicitacaoInformacao, RespostaFarmaceutic
from prompts import PROMPT_CHAT_AGENT

from langchain.agents.structured_output import ProviderStrategy

load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    raise RuntimeError(
        "A variável GEMINI_API_KEY não foi encontrada no arquivo .env"
    )

modelo = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

agente_maestro = create_agent(
    model=modelo,
    system_prompt= PROMPT_CHAT_AGENT,
    response_format=ProviderStrategy(RespostaFarmaceutic),
)

def gerar_informacao(solicitacao: SolicitacaoInformacao) -> RespostaFarmaceutic:
    mensagem_usuario = f"""
    Medicamento: {solicitacao.medicamento}
    Forma Farmaceutica: {solicitacao.forma_farmaceutica}
    Pergunta: {solicitacao.pergunta}
    """

    vetorial_content = buscar_bula(
        solicitacao.pergunta,
        solicitacao.medicamento,
        solicitacao.forma_farmaceutica,
        quantidade=3,
    )

    if not vetorial_content:
        return RespostaFarmaceutic(
            explicacao=(
                "Não encontrei conteúdo indexado para o medicamento e a "
                "forma farmacêutica informados."
            )
        )

    mensagem_usuario += "\n\nContexto recuperado da Bula:\n"
    for i, documento in enumerate(vetorial_content, start=1):
        mensagem_usuario += f"{i}. {documento.page_content} {documento.metadata.get('source', 'Fonte não informada')}\n"

    resultado = agente_maestro.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": mensagem_usuario,
                }
            ]
        }
    )

    return resultado["structured_response"]
