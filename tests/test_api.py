import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api import app
from models import RespostaFarmaceutic


class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cliente = TestClient(app)

    @patch("api.gerar_informacao")
    def test_consulta_devolve_resposta_e_fontes(self, gerar_informacao) -> None:
        gerar_informacao.return_value = (
            RespostaFarmaceutic(explicacao="Resposta fundamentada na bula."),
            [
                Document(
                    page_content="Trecho exato recuperado.",
                    metadata={
                        "medicamento": "Dorflex",
                        "forma_farmaceutica": "comprimido",
                        "section_number": 8,
                        "section_title": "POSOLOGIA E MODO DE USAR",
                        "arquivo_nome": "004-dorflex-profissional.pdf",
                        "chunk_id": "1.8.1.1",
                    },
                )
            ],
        )

        resposta = self.cliente.post(
            "/api/consultas",
            json={
                "medicamento": "Dorflex",
                "forma_farmaceutica": "comprimido",
                "pergunta": "Como devo tomar?",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.json()
        self.assertEqual(conteudo["resposta"], "Resposta fundamentada na bula.")
        self.assertEqual(conteudo["fontes"][0]["secao_numero"], 8)
        self.assertEqual(conteudo["fontes"][0]["trecho"], "Trecho exato recuperado.")
        gerar_informacao.assert_called_once()
        solicitacao = gerar_informacao.call_args.args[0]
        self.assertEqual(solicitacao.pergunta, "Como devo tomar?")

    @patch("api.listar_catalogo_medicamentos")
    def test_lista_catalogo_indexado(self, listar_catalogo) -> None:
        listar_catalogo.return_value = [
            {
                "id": "med_123",
                "nome": "Dorflex",
                "nome_comercial": "Dorflex",
                "principio_ativo": "dipirona + orfenadrina + cafeína",
                "aliases": ["Dorflex"],
                "numero_registro": "123456",
                "fabricante": "Fabricante",
                "apresentacoes": [
                    {
                        "id": "bula_123",
                        "forma": "comprimido",
                        "concentracao": "300 mg + 35 mg + 50 mg",
                        "via_administracao": "oral",
                        "tipo_bula": "profissional",
                    }
                ],
            }
        ]

        resposta = self.cliente.get("/api/medicamentos")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()[0]["nome"], "Dorflex")
        self.assertEqual(resposta.json()[0]["id"], "med_123")


if __name__ == "__main__":
    unittest.main()
