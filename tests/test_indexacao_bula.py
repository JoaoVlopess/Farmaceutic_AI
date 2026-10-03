import unittest

from langchain_core.documents import Document

from RAG.indexar_documento import dividir_bula
from utils import identificar_forma_farmaceutica, normalizar_nome_medicamento


class IndexacaoBulaTest(unittest.TestCase):
    def test_normaliza_nome_para_filtro(self):
        self.assertEqual(normalizar_nome_medicamento("Dórflex MAX®"), "dorflex max")

    def test_identifica_forma_farmaceutica(self):
        self.assertEqual(
            identificar_forma_farmaceutica(
                "DORFLEX\nAPRESENTAÇÃO\nSolução oral (gotas) em frasco."
            ),
            "gotas",
        )

    def test_chunks_herdam_medicamento_e_preservam_composicao(self):
        documento = Document(
            page_content=(
                "REMÉDIO X\nAPRESENTAÇÕES\nCaixa com 10 comprimidos.\n"
                "COMPOSIÇÃO\nSubstância X.\n\n"
                "1. INDICAÇÕES\nÉ indicado para teste."
            ),
            metadata={
                "source": "bula.pdf",
                "bula_index": 1,
                "medicamento": "REMÉDIO X",
                "medicamento_normalizado": "remedio x",
                "forma_farmaceutica": "comprimido",
            },
        )

        chunks = dividir_bula(documento)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].metadata["medicamento"], "REMÉDIO X")
        self.assertEqual(chunks[0].metadata["medicamento_normalizado"], "remedio x")
        self.assertEqual(chunks[0].metadata["section_number"], 0)
        self.assertIn("COMPOSIÇÃO", chunks[0].page_content)
        self.assertTrue(all(chunk.id for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
