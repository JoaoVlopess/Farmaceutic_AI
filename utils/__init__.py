"""Utilitários compartilhados pelo projeto."""

from .limpeza_bula import (
    eh_inicio_conteudo_bula,
    eh_inicio_historico_bula,
    filtrar_paginas_bula,
    limpar_pagina_bula,
    limpar_texto_bula,
    normalizar_espacos,
    remover_cabecalhos_e_rodapes,
    remover_dizeres_legais,
)
from .medicamentos import (
    identificar_forma_farmaceutica,
    identificar_nome_medicamento,
    normalizar_nome_medicamento,
)

__all__ = [
    "eh_inicio_conteudo_bula",
    "eh_inicio_historico_bula",
    "filtrar_paginas_bula",
    "limpar_pagina_bula",
    "limpar_texto_bula",
    "normalizar_espacos",
    "remover_cabecalhos_e_rodapes",
    "remover_dizeres_legais",
    "identificar_nome_medicamento",
    "identificar_forma_farmaceutica",
    "normalizar_nome_medicamento",
]
