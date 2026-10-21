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

    def test_secoes_repetidas_recebem_ids_unicos(self):
        documento = Document(
            page_content=(
                "1. INDICAÇÕES\nPrimeira versão.\n\n"
                "1. INDICAÇÕES\nSegunda versão."
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

        self.assertEqual(len(chunks), 2)
        self.assertEqual(len({chunk.id for chunk in chunks}), 2)
        self.assertEqual(
            [chunk.metadata["chunk_id"] for chunk in chunks],
            ["1.1.1.1", "1.1.2.1"],
        )

    def test_chunks_de_pdf_preservam_numero_da_pagina(self):
        documento = Document(
            page_content=(
                "<<<PAGINA_PDF:2>>>\n1. INDICAÇÕES\nPrimeira página.\n\n"
                "<<<PAGINA_PDF:3>>>\nContinuação da indicação."
            ),
            metadata={
                "source": "bula.pdf",
                "arquivo_id": "abc",
                "bula_index": 1,
                "medicamento": "REMÉDIO X",
                "medicamento_normalizado": "remedio x",
                "forma_farmaceutica": "comprimido",
            },
        )

        chunks = dividir_bula(documento)

        self.assertEqual([chunk.metadata["pagina_pdf"] for chunk in chunks], [2, 3])
        self.assertEqual(chunks[1].metadata["section_number"], 1)


if __name__ == "__main__":
    unittest.main()
