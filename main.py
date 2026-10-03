from models import SolicitacaoInformacao
from services import gerar_informacao


def main() -> None:
    solicitacao = SolicitacaoInformacao(
        medicamento="Dorflex",
        forma_farmaceutica="comprimido",
        pergunta="A medicação tem algum efeito colateral?",
    )

    resposta = gerar_informacao(solicitacao)
    print(resposta.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
