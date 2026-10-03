"""Identificação e normalização de nomes de medicamentos."""

from __future__ import annotations

import re
import unicodedata


def normalizar_nome_medicamento(nome: str) -> str:
    """Cria uma chave estável para filtros no banco vetorial."""
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(char for char in nome if not unicodedata.combining(char))
    nome = nome.casefold().replace("®", "").replace("™", "")
    nome = re.sub(r"[^a-z0-9]+", " ", nome)
    return re.sub(r"\s+", " ", nome).strip()


def identificar_forma_farmaceutica(texto_bula: str) -> str:
    """Identifica uma forma farmacêutica comum no bloco de apresentações."""
    comparavel = normalizar_nome_medicamento(texto_bula)
    inicio = re.search(r"\bap\s*resentac(?:ao|oes)\b", comparavel)
    trecho = comparavel[inicio.end() : inicio.end() + 500] if inicio else comparavel[:500]

    formas = (
        (r"\b(?:solucao oral[^.]{0,80})?gotas?\b", "gotas"),
        (r"\bpastilhas?\b", "pastilha"),
        (r"\bcomprimidos?\b", "comprimido"),
        (r"\bcapsulas?\b", "cápsula"),
        (r"\bxarope\b", "xarope"),
        (r"\bsuspensao oral\b", "suspensão oral"),
        (r"\bsolucao oral\b", "solução oral"),
        (r"\bcreme\b", "creme"),
        (r"\bpomada\b", "pomada"),
        (r"\bgel\b", "gel"),
        (r"\binjetavel\b", "injetável"),
    )
    for padrao, forma in formas:
        if re.search(padrao, trecho):
            return forma

    return "não identificada"


def identificar_nome_medicamento(texto_bula: str) -> str:
    """Obtém o nome comercial a partir das primeiras linhas da bula.

    Nas bulas do Bulário, o nome comercial aparece como a primeira linha útil
    da capa ou da página que contém apresentações e composição.
    """
    for linha in texto_bula.splitlines()[:20]:
        nome = linha.strip().replace("®", "").replace("™", "").strip()
        if not nome:
            continue
        if nome.upper() in {"BULA", "BULA DO PACIENTE", "BULA DO PROFISSIONAL"}:
            continue
        if len(nome) <= 100:
            return nome

    raise ValueError("Não foi possível identificar o medicamento na bula.")
