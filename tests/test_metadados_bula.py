import unittest

from utils import construir_metadados_bula


class MetadadosBulaTest(unittest.TestCase):
    def test_prioriza_cadastro_e_extrai_campos_estruturados(self):
        texto = """TANDRILAX
Achê Laboratórios Farmacêuticos S.A.
I - IDENTIFICAÇÃO DO MEDICAMENTO
TANDRILAX
cafeína
carisoprodol
diclofenaco sódico
paracetamol
USO ORAL
APRESENTAÇÕES
Comprimidos com 30 mg + 125 mg + 50 mg + 300 mg.
"""
        cadastro = {
            "id": "016",
            "principal": "Tandrilax",
            "termosBusca": ["Tandrilax"],
            "slug": "tandrilax",
            "resultado": {
                "nomeEncontrado": "TANDRILAX",
                "numeroRegistro": "105730005",
            },
        }

        metadata = construir_metadados_bula(
            texto,
            "bulas_pdf/016-tandrilax-profissional.pdf",
            "a" * 64,
            1,
            nome_atual="AAS",
            cadastro=cadastro,
        )

        self.assertEqual(metadata["nome_comercial"], "TANDRILAX")
        self.assertIn("diclofenaco sódico", metadata["principio_ativo"])
        self.assertEqual(metadata["via_administracao"], "oral")
        self.assertEqual(metadata["numero_registro"], "105730005")
        self.assertEqual(metadata["tipo_bula"], "profissional")
        self.assertTrue(str(metadata["medicamento_id"]).startswith("med_"))


if __name__ == "__main__":
    unittest.main()
