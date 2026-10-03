from models import SolicitacaoInformacao
from services import gerar_informacao
# from tools.musica import transpor_nota


solicitacao = SolicitacaoInformacao(
    medicamento = "Dorflex",
    forma_farmaceutica = "comprimido",
    pergunta = "Qual a periodicidade que eu devo tomar dorflex?"
)

print(gerar_informacao(solicitacao))