from pydantic import BaseModel

class SolicitacaoInformacao(BaseModel):
    medicamento: str
    forma_farmaceutica: str
    pergunta: str
    medicamento_id: str | None = None
    bula_id: str | None = None


class RespostaFarmaceutic(BaseModel):
    explicacao: str
