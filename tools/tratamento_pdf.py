#tools/tratamento/pdf

"""Ferramentas de extração e tratamento de PDFs de bulas."""

from pathlib import Path

from pypdf import PdfReader

from utils import filtrar_paginas_bula, normalizar_espacos


def extrair_paginas_pdf(caminho_pdf: str | Path) -> list[str]:
    """Extrai o texto de cada página, mantendo seus limites."""
    reader = PdfReader(caminho_pdf)
    return [pagina.extract_text() or "" for pagina in reader.pages]


def extrair_texto_pdf(caminho_pdf: str | Path, limpar: bool = True) -> str:
    """Extrai uma bula em texto, removendo ruído administrativo por padrão.

    Args:
        caminho_pdf: Caminho do arquivo PDF.
        limpar: Se ``True``, remove históricos de alterações, dizeres legais,
            números de página e outros marcadores sem valor para o RAG.

    Returns:
        O texto das páginas separado por uma linha vazia.
    """
    paginas = extrair_paginas_pdf(caminho_pdf)
    if limpar:
        paginas = filtrar_paginas_bula(paginas)
    else:
        paginas = [normalizar_espacos(pagina) for pagina in paginas if pagina.strip()]

    return "\n\n".join(paginas)
