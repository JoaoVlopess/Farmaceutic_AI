import unittest

from utils.limpeza_bula import (
    filtrar_paginas_bula,
    limpar_pagina_bula,
    limpar_texto_bula,
)


class LimpezaBulaTest(unittest.TestCase):
    def test_remove_dizeres_legais_sem_apagar_conteudo_clinico(self):
        texto = "9. REAÇÕES ADVERSAS\nProcure um médico.\nDIZERES LEGAIS\nCNPJ: 00"

        self.assertEqual(
            limpar_pagina_bula(texto),
            "9. REAÇÕES ADVERSAS\nProcure um médico.",
        )

    def test_remove_bloco_iniciado_por_registro(self):
        texto = "Em caso de intoxicação, procure ajuda.\nRegistro: 1.2345.6789\nProduzido por: X"

        self.assertEqual(
            limpar_pagina_bula(texto),
            "Em caso de intoxicação, procure ajuda.",
        )

    def test_remove_historico_multipagina_e_retorna_ao_conteudo(self):
        paginas = [
            "APRESENTAÇÕES\nUSO ORAL\nCOMPOSIÇÃO\nTexto A",
            "Anexo B\nHistórico de Alteração da Bula\nTabela",
            "Continuação da tabela\n10451 - MEDICAMENTO NOVO",
            "Capa da segunda apresentação",
            "APRESENTAÇÃO\nUSO ORAL\nCOMPOSIÇÃO\nTexto B",
        ]

        resultado = filtrar_paginas_bula(paginas)

        self.assertEqual(len(resultado), 2)
        self.assertIn("Texto A", resultado[0])
        self.assertIn("Texto B", resultado[1])

    def test_remove_continuacao_dos_dizeres_na_pagina_seguinte(self):
        paginas = [
            "Reação adversa importante\nDIZERES LEGAIS\nFabricado por: X",
            "Endereço do fabricante\nEsta bula foi aprovada pela ANVISA.",
            "Histórico de Alterações da Bula\nTabela",
        ]

        self.assertEqual(filtrar_paginas_bula(paginas), ["Reação adversa importante"])

    def test_preserva_numero_isolado_no_meio_do_conteudo(self):
        texto = "Administrar\n1\ncomprimido por dia."

        self.assertEqual(limpar_pagina_bula(texto), texto)

    def test_limpa_texto_ja_extraido_a_partir_do_historico(self):
        texto = "Conteúdo útil\nAnexo B\nHistórico de Alterações da Bula\nTabela"

        self.assertEqual(limpar_texto_bula(texto), "Conteúdo útil")


if __name__ == "__main__":
    unittest.main()
