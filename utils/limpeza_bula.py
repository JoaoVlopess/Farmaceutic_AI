"""Funções de limpeza para textos de bulas extraídos de PDFs da Anvisa."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


_MARCADOR_HISTORICO = re.compile(
    r"(?:\bANEXO\s+[A-Z]\b[\s\S]{0,150})?"
    r"\bHISTORICO\s+(?:DE\s+)?ALTERAC(?:AO|OES)\s+"
    r"(?:(?:DA|DE)\s+|PARA\s+A\s+)?BULA\b",
    flags=re.IGNORECASE,
)

_DIZERES_LEGAIS = re.compile(
    r"(?im)^\s*DIZERES\s+LEGAIS\s*:?[ \t]*$[\s\S]*\Z"
)

# Algumas bulas não imprimem o título "Dizeres legais". Nesses casos, o
# número de registro é o primeiro item do bloco administrativo final.
_REGISTRO_NO_FIM = re.compile(
    r"(?im)^\s*(?:REGISTRO(?:\s+(?:MS|ANVISA))?|REG\.?\s*MS)\s*:\s*"
    r"\d[\d.\-/ ]*\.?[ \t]*$[\s\S]*\Z"
)

_CABECALHO_RODAPE = re.compile(
    r"(?im)^[ \t]*(?:"
    r"INTERNAL|"
    r"P[ÁA]GINA\s+\d+\s*(?:DE\s+\d+)?|"
    r"-\s*\d+\s+DE\s+\d+\s*-"
    r")[ \t]*$"
)

_NUMERO_PAGINA_ISOLADO = re.compile(
    r"(?:\A[ \t\n]*\d+[ \t]*(?:\n|\Z))|(?:\n[ \t]*\d+[ \t]*\Z)"
)


def _sem_acentos(texto: str) -> str:
    """Gera uma versão comparável sem alterar o texto que será indexado."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(char for char in normalizado if not unicodedata.combining(char))


def normalizar_espacos(texto: str) -> str:
    """Normaliza espaços e linhas vazias preservando parágrafos e títulos."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = texto.replace("\xa0", " ").replace("\x00", "")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def remover_cabecalhos_e_rodapes(texto: str) -> str:
    """Remove marcadores internos e numeração isolada gerada pelo PDF."""
    texto = _CABECALHO_RODAPE.sub("", texto)
    texto = _NUMERO_PAGINA_ISOLADO.sub("\n", texto)
    return normalizar_espacos(texto)


def remover_dizeres_legais(texto: str) -> str:
    """Remove o bloco cadastral/legal, mantendo o conteúdo clínico anterior."""
    inicio = _inicio_dizeres_legais(texto)
    if inicio is not None:
        texto = texto[:inicio]

    return normalizar_espacos(texto)


def _inicio_dizeres_legais(texto: str) -> int | None:
    """Retorna o índice inicial do bloco legal, quando presente."""
    texto_comparavel = _sem_acentos(texto)
    correspondencias = [
        correspondencia
        for padrao in (_DIZERES_LEGAIS, _REGISTRO_NO_FIM)
        if (correspondencia := padrao.search(texto_comparavel)) is not None
    ]
    if not correspondencias:
        return None
    return min(correspondencia.start() for correspondencia in correspondencias)


def eh_inicio_historico_bula(texto: str) -> bool:
    """Indica se a página inicia um anexo de histórico de alterações."""
    trecho_inicial = _sem_acentos(texto[:1000])
    return _MARCADOR_HISTORICO.search(trecho_inicial) is not None


def eh_inicio_conteudo_bula(texto: str) -> bool:
    """Reconhece o reinício de uma bula após um histórico multipágina.

    Os três marcadores em conjunto evitam confundir a coluna "Itens da bula"
    do próprio histórico com conteúdo farmacêutico de fato.
    """
    comparavel = _sem_acentos(texto).upper()
    tem_apresentacao = re.search(r"\bAPRESENTAC(?:AO|OES)\b", comparavel) is not None
    return tem_apresentacao and "COMPOSICAO" in comparavel and "USO " in comparavel


def limpar_pagina_bula(texto: str) -> str:
    """Limpa ruído visual e informações legais de uma página de bula."""
    texto = remover_cabecalhos_e_rodapes(texto)
    return remover_dizeres_legais(texto)


def filtrar_paginas_bula(paginas: Iterable[str]) -> list[str]:
    """Remove anexos históricos e limpa as páginas clínicas restantes.

    O estado de histórico é necessário porque esses anexos normalmente duram
    várias páginas, mas somente a primeira contém seu título. Caso o PDF reúna
    mais de uma bula, a leitura recomeça na próxima página que apresente os
    marcadores usuais de conteúdo.
    """
    paginas_limpas: list[str] = []
    dentro_do_historico = False
    dentro_dos_dizeres_legais = False

    for pagina in paginas:
        if eh_inicio_historico_bula(pagina):
            dentro_do_historico = True
            dentro_dos_dizeres_legais = False
            continue

        if dentro_do_historico:
            if not eh_inicio_conteudo_bula(pagina):
                continue
            dentro_do_historico = False

        if dentro_dos_dizeres_legais:
            if not eh_inicio_conteudo_bula(pagina):
                continue
            dentro_dos_dizeres_legais = False

        pagina_limpa = limpar_pagina_bula(pagina)
        if pagina_limpa:
            paginas_limpas.append(pagina_limpa)
        if _inicio_dizeres_legais(pagina) is not None:
            dentro_dos_dizeres_legais = True

    return paginas_limpas


def limpar_texto_bula(texto: str) -> str:
    """Limpa um texto sem informação de páginas.

    Esta versão é útil para textos já extraídos. Para PDFs, prefira
    ``filtrar_paginas_bula``, pois ela remove históricos multipágina com mais
    precisão.
    """
    texto = remover_cabecalhos_e_rodapes(texto)
    comparavel = _sem_acentos(texto)
    marcador = _MARCADOR_HISTORICO.search(comparavel)
    if marcador:
        texto = texto[: marcador.start()]
    return remover_dizeres_legais(texto)
