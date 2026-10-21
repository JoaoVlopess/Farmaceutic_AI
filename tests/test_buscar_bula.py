import unittest
from unittest.mock import Mock, patch

from RAG.buscar_bula import buscar_bula


class BuscarBulaTest(unittest.TestCase):
    @patch("RAG.buscar_bula.obter_banco_vetorial")
    def test_busca_filtra_medicamento_e_forma(self, obter_banco: Mock):
        banco = obter_banco.return_value
        banco.similarity_search.return_value = []

        buscar_bula(
            "Como devo tomar?",
            medicamento="Dórflex®",
            forma_farmaceutica="comprimido",
        )

        banco.similarity_search.assert_called_once_with(
            query="Como devo tomar?",
            k=3,
            filter={
                "$and": [
                    {"medicamento_normalizado": "dorflex"},
                    {"forma_farmaceutica": "comprimido"},
                ]
            },
        )

    @patch("RAG.buscar_bula.obter_banco_vetorial")
    def test_busca_por_id_estavel_restringe_a_bula_profissional(
        self, obter_banco: Mock
    ):
        banco = obter_banco.return_value
        banco.similarity_search.return_value = []

        buscar_bula(
            "Quais são as contraindicações?",
            medicamento="texto exibido não usado como filtro",
            medicamento_id="med_123",
            bula_id="bula_456",
        )

        banco.similarity_search.assert_called_once_with(
            query="Quais são as contraindicações?",
            k=3,
            filter={
                "$and": [
                    {"bula_id": "bula_456"},
                    {"tipo_bula": "profissional"},
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
