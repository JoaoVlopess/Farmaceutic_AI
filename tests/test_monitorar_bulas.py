import unittest
from pathlib import Path
from unittest.mock import patch

from RAG.indexar_documento import ResultadoIndexacao
from RAG.monitorar_bulas import MonitorDeBulas, processar_e_apagar_pdf


class MonitorarBulasTest(unittest.TestCase):
    @patch("RAG.monitorar_bulas.indexar_pdf")
    def test_apaga_pdf_somente_depois_da_confirmacao(self, indexar_pdf):
        pasta = Path("tests").resolve()
        pdf = pasta / "bula_monitor_teste.pdf"
        indexar_pdf.return_value = ResultadoIndexacao(
            arquivo=pdf,
            medicamentos=("Remédio (comprimido)",),
            quantidade_bulas=1,
            quantidade_chunks=2,
            ids=("1", "2"),
        )

        with patch.object(Path, "unlink") as unlink:
            processar_e_apagar_pdf(pdf, pasta)
            unlink.assert_called_once_with(missing_ok=True)

    @patch("RAG.monitorar_bulas.indexar_pdf", side_effect=RuntimeError("falhou"))
    def test_mantem_pdf_quando_indexacao_falha(self, _indexar_pdf):
        pasta = Path("tests").resolve()
        pdf = pasta / "bula_monitor_teste.pdf"
        with patch.object(Path, "unlink") as unlink:
            with self.assertRaises(RuntimeError):
                processar_e_apagar_pdf(pdf, pasta)
            unlink.assert_not_called()

    def test_reconhece_erro_de_cota_e_retry_delay(self):
        erro = RuntimeError(
            "429 RESOURCE_EXHAUSTED retryDelay': '12s'"
        )

        self.assertTrue(MonitorDeBulas._eh_erro_de_cota(erro))
        self.assertEqual(MonitorDeBulas._espera_informada_pela_api(erro), 12.0)


if __name__ == "__main__":
    unittest.main()
