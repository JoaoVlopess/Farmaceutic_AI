from pydantic import BaseModel

class SolicitacaoInformacao(BaseModel):
    medicamento: str
    forma_farmaceutica: str
    pergunta: str


class RespostaFarmaceutic(BaseModel):
    explicacao: str