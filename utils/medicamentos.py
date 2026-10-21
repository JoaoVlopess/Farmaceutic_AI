"""Identificação e normalização de metadados farmacêuticos."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


_ROTULOS_INVALIDOS = re.compile(
    r"(?:^bula(?:_|\s)|identifica[cç][aã]o do medicamento|"
    r"profissional (?:da|de) sa[uú]de|modelo de bula|"
    r"^v[._-]?\d|^bu\d+[\/_-])",
    flags=re.IGNORECASE,
)


def normalizar_nome_medicamento(nome: str) -> str:
    """Cria uma chave estável, sem acentos, marcas ou pontuação."""
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(char for char in nome if not unicodedata.combining(char))
    nome = nome.casefold().replace("®", "").replace("™", "")
    nome = re.sub(r"[^a-z0-9]+", " ", nome)
    return re.sub(r"\s+", " ", nome).strip()


def nome_medicamento_eh_invalido(nome: str) -> bool:
    """Detecta cabeçalhos e códigos que não podem ser nomes de medicamento."""
    limpo = nome.strip()
    return not limpo or bool(_ROTULOS_INVALIDOS.search(limpo))


def identificar_forma_farmaceutica(texto_bula: str) -> str:
    """Identifica uma forma farmacêutica no bloco de apresentações."""
    comparavel = normalizar_nome_medicamento(texto_bula)
    inicio = re.search(r"\bap\s*resentac(?:ao|oes)\b", comparavel)
    trecho = comparavel[inicio.end() : inicio.end() + 900] if inicio else comparavel[:900]

    formas = (
        (r"\bsuspensao oral\b", "suspensão oral"),
        (r"\bsolucao para nebulizacao\b", "solução para nebulização"),
        (r"\bsolucao injetavel\b", "solução injetável"),
        (r"\bsolucao oral[^.]{0,100}\bgotas?\b", "gotas"),
        (r"\bgotas?\b", "gotas"),
        (r"\bpastilhas?\b", "pastilha"),
        (r"\bcomprimidos?\b", "comprimido"),
        (r"\bcapsulas?\b", "cápsula"),
        (r"\bxarope\b", "xarope"),
        (r"\bsolucao oral\b", "solução oral"),
        (r"\bcreme\b", "creme"),
        (r"\bpomada\b", "pomada"),
        (r"\bgel\b", "gel"),
        (r"\binjetavel\b", "injetável"),
        (r"\bpo para solucao\b", "pó para solução"),
    )
    for padrao, forma in formas:
        if re.search(padrao, trecho):
            return forma

    return "não identificada"


def identificar_nome_medicamento(
    texto_bula: str,
    nomes_preferenciais: Iterable[str] = (),
) -> str:
    """Identifica o produto, priorizando nomes obtidos no download da Anvisa."""
    linhas = [
        linha.strip().replace("®", "").replace("™", "").strip()
        for linha in texto_bula.splitlines()[:80]
        if linha.strip()
    ]
    preferencias = [nome for nome in nomes_preferenciais if nome and nome.strip()]

    for preferencia in preferencias:
        chave = normalizar_nome_medicamento(preferencia)
        for linha in linhas:
            chave_linha = normalizar_nome_medicamento(linha)
            if chave_linha == chave or chave_linha.startswith(f"{chave} "):
                if len(linha) <= 100 and not nome_medicamento_eh_invalido(linha):
                    return linha

    descartes = {
        "bula",
        "bula do paciente",
        "bula do profissional",
        "bula para profissional de saude",
        "bula para o profissional de saude",
        "informacoes tecnicas aos profissionais de saude",
        "apresentacao",
        "apresentacoes",
    }
    for linha in linhas:
        chave = normalizar_nome_medicamento(linha)
        if chave in descartes or nome_medicamento_eh_invalido(linha):
            continue
        if re.fullmatch(r"[ivx]+\s*[-–].*", chave):
            continue
        if len(linha) <= 100:
            return linha

    if preferencias:
        return preferencias[0].strip()
    raise ValueError("Não foi possível identificar o medicamento na bula.")


def identificar_principio_ativo(
    texto_bula: str,
    nome_comercial: str,
    principio_fallback: str = "",
) -> str:
    """Extrai princípio(s) ativo(s), mantendo vazio quando não há confiança."""
    fallback_igual_ao_nome = bool(principio_fallback) and (
        normalizar_nome_medicamento(principio_fallback)
        == normalizar_nome_medicamento(nome_comercial)
    )
    if principio_fallback and (
        not fallback_igual_ao_nome
    ):
        return principio_fallback.strip()
    if fallback_igual_ao_nome and "medicamento generico" in normalizar_nome_medicamento(
        texto_bula[:5000]
    ):
        return principio_fallback.strip()

    nome_escapado = re.escape(nome_comercial.replace("®", "").strip())
    parenteses = re.search(
        rf"{nome_escapado}\s*[®™]?\s*\n\s*\(([^)\n]{{3,180}})\)",
        texto_bula,
        flags=re.IGNORECASE,
    )
    if parenteses and not re.search(r"\d\s*(?:mg|g|ml)", parenteses.group(1), re.I):
        return re.sub(r"\s+", " ", parenteses.group(1)).strip()

    linhas = [linha.strip() for linha in texto_bula.splitlines()]
    chave_nome = normalizar_nome_medicamento(nome_comercial)
    melhores: list[str] = []
    paradas = re.compile(
        r"^(?:apresenta[cç][aã]o|composi[cç][aã]o|uso |medicamento |"
        r"bula |i\s*[-–]|ii\s*[-–])",
        flags=re.IGNORECASE,
    )
    ruido = re.compile(
        r"(?:ltda|laborat[oó]rios?|farmac[eê]utic|comprimido|c[aá]psula|"
        r"solu[cç][aã]o|suspens[aã]o|\d\s*(?:mg|g|ml)|resolu[cç][aã]o|"
        r"medicamento gen[eé]rico|apresenta[cç][aã](?:o|ões)|embalagem|formula[cç][aã]o)",
        flags=re.IGNORECASE,
    )

    for indice, linha in enumerate(linhas):
        if normalizar_nome_medicamento(linha) != chave_nome:
            continue
        candidatos: list[str] = []
        for seguinte in linhas[indice + 1 : indice + 8]:
            seguinte = seguinte.strip(" ()")
            if not seguinte:
                continue
            if paradas.search(seguinte):
                break
            if (
                ruido.search(seguinte)
                or len(seguinte) > 70
                or "_" in seguinte
                or seguinte.startswith(("*", "\"", "“"))
                or seguinte.endswith(".")
                or seguinte.endswith(":")
                or nome_medicamento_eh_invalido(seguinte)
            ):
                continue
            if re.search(r"[A-Za-zÀ-ÿ]", seguinte):
                candidatos.append(seguinte)
        if len(candidatos) > len(melhores):
            melhores = candidatos

    if melhores:
        return " + ".join(dict.fromkeys(melhores))
    return ""


def identificar_concentracao(texto_bula: str) -> str:
    """Obtém a primeira concentração declarada nas apresentações."""
    comparavel = texto_bula[:3500]
    inicio = re.search(r"APRESENTA(?:ÇÃO|ÇÕES)", comparavel, flags=re.IGNORECASE)
    if inicio:
        comparavel = comparavel[inicio.end() : inicio.end() + 1000]
    unidade = r"(?:mg|mcg|µg|g|UI|U)(?:\s*/\s*(?:mL|dose|g))?"
    item = rf"\d+(?:[,.]\d+)?\s*{unidade}"
    correspondencia = re.search(
        rf"({item}(?:\s*\+\s*{item}){{0,5}})",
        comparavel,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", correspondencia.group(1)).strip() if correspondencia else ""


def identificar_via_administracao(texto_bula: str) -> str:
    """Identifica a via declarada em expressões como ``USO ORAL``."""
    comparavel = normalizar_nome_medicamento(texto_bula[:5000])
    vias = (
        ("uso intravenoso", "intravenosa"),
        ("uso intramuscular", "intramuscular"),
        ("uso subcutaneo", "subcutânea"),
        ("uso inalatorio", "inalatória"),
        ("uso topico", "tópica"),
        ("uso dermatologico", "dermatológica"),
        ("uso oftalmico", "oftálmica"),
        ("uso nasal", "nasal"),
        ("uso retal", "retal"),
        ("uso vaginal", "vaginal"),
        ("uso oral", "oral"),
    )
    return next((rotulo for marcador, rotulo in vias if marcador in comparavel), "")


def identificar_fabricante(texto_bula: str) -> str:
    """Busca a empresa exibida no cabeçalho da bula."""
    for linha in texto_bula.splitlines()[:50]:
        limpa = linha.strip()
        if re.search(
            r"\b(?:Ltda\.?|S\.?\s*A\.?|Laborat[oó]rios?|Pharma|Healthcare)\b",
            limpa,
            flags=re.IGNORECASE,
        ) and len(limpa) <= 140:
            return limpa
    return ""


def identificar_tipo_bula(texto_bula: str, nome_arquivo: str = "") -> str:
    """Classifica a bula como profissional, paciente ou não identificada."""
    comparavel = normalizar_nome_medicamento(f"{nome_arquivo}\n{texto_bula[:12000]}")
    if "profissional" in normalizar_nome_medicamento(nome_arquivo):
        return "profissional"
    if re.search(r"informacoes tecnicas aos profissionais|bula para o profissional", comparavel):
        return "profissional"
    if re.search(r"informacoes ao paciente|bula do paciente", comparavel):
        return "paciente"
    return "não identificada"


def identificar_versao_data(texto_bula: str) -> tuple[str, str]:
    """Extrai marcadores editoriais de versão e data quando explícitos."""
    trecho = texto_bula[:5000]
    versao = re.search(
        r"\b((?:V(?:ERSÃO)?|BU)\s*[._/-]?\s*[A-Z0-9][A-Z0-9._/-]{1,30})\b",
        trecho,
        flags=re.IGNORECASE,
    )
    data = re.search(r"\b((?:0?[1-9]|[12]\d|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:20)?\d{2})\b", trecho)
    if not data:
        data = re.search(r"\b((?:0?[1-9]|1[0-2])[/.-]20\d{2})\b", trecho)
    return (
        re.sub(r"\s+", "", versao.group(1)) if versao else "",
        data.group(1) if data else "",
    )
