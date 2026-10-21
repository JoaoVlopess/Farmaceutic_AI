"""Construção do esquema versionado de metadados das bulas."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .medicamentos import (
    identificar_concentracao,
    identificar_fabricante,
    identificar_forma_farmaceutica,
    identificar_nome_medicamento,
    identificar_principio_ativo,
    identificar_tipo_bula,
    identificar_versao_data,
    identificar_via_administracao,
    nome_medicamento_eh_invalido,
    normalizar_nome_medicamento,
)


VERSAO_ESQUEMA_METADADOS = 2
ARQUIVO_ESTADO_PADRAO = Path("bulas_pdf/estado-profissional.json")


def _valor_textual(valor: Any) -> str:
    return str(valor).strip() if valor is not None else ""


def carregar_cadastro_download(
    caminho_arquivo: str | Path,
    caminho_estado: str | Path = ARQUIVO_ESTADO_PADRAO,
) -> dict[str, Any]:
    """Localiza no relatório do download os dados cadastrais do PDF."""
    estado = Path(caminho_estado)
    if not estado.exists():
        return {}

    try:
        conteudo = json.loads(estado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    nome_arquivo = Path(caminho_arquivo).name.casefold()
    prefixo = re.match(r"^(\d{3})-", nome_arquivo)
    for item in conteudo.get("itens", []):
        if prefixo and _valor_textual(item.get("id")) == prefixo.group(1):
            return item
        resultado = item.get("resultado") or {}
        for arquivo in (resultado.get("arquivos") or {}).values():
            if Path(_valor_textual(arquivo.get("caminho"))).name.casefold() == nome_arquivo:
                return item
    return {}


def aliases_para_lista(valor: Any) -> list[str]:
    """Desserializa aliases armazenados no formato compatível com Chroma."""
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    if not valor:
        return []
    try:
        itens = json.loads(str(valor))
    except (TypeError, ValueError):
        itens = str(valor).split("|")
    return [str(item).strip() for item in itens if str(item).strip()]


def _aliases_unicos(*grupos: Any) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []
    for grupo in grupos:
        valores = grupo if isinstance(grupo, (list, tuple, set)) else [grupo]
        for valor in valores:
            texto = _valor_textual(valor)
            chave = normalizar_nome_medicamento(texto)
            if texto and chave and chave not in vistos:
                vistos.add(chave)
                resultado.append(texto)
    return resultado


def _nome_cadastrado(cadastro: dict[str, Any]) -> str:
    resultado = cadastro.get("resultado") or {}
    return (
        _valor_textual(resultado.get("nomeEncontrado"))
        or _valor_textual(cadastro.get("principal"))
    )


def resolver_nome_comercial(
    texto: str,
    cadastro: dict[str, Any],
    nome_atual: str = "",
) -> str:
    """Resolve nomes ruins usando cadastro, arquivo e conteúdo da bula."""
    resultado = cadastro.get("resultado") or {}
    preferencias = _aliases_unicos(
        resultado.get("nomeEncontrado"),
        cadastro.get("principal"),
        cadastro.get("termosBusca") or [],
    )

    atual = _valor_textual(nome_atual)
    slug = normalizar_nome_medicamento(_valor_textual(cadastro.get("slug")))
    atual_compativel = atual and not nome_medicamento_eh_invalido(atual)
    if atual_compativel and preferencias:
        chave_atual = normalizar_nome_medicamento(atual)
        chaves_preferenciais = [normalizar_nome_medicamento(nome) for nome in preferencias]
        atual_compativel = any(
            chave_atual == chave
            or chave_atual.startswith(f"{chave} ")
            or (slug and slug in chave_atual)
            for chave in chaves_preferenciais
        )

    if atual_compativel:
        preferencias.insert(0, atual)

    try:
        identificado = identificar_nome_medicamento(texto, preferencias)
    except ValueError:
        identificado = ""

    if identificado and not nome_medicamento_eh_invalido(identificado):
        chave_identificada = normalizar_nome_medicamento(identificado)
        if not preferencias or any(
            chave_identificada == normalizar_nome_medicamento(nome)
            or chave_identificada.startswith(
                f"{normalizar_nome_medicamento(nome)} "
            )
            or (slug and slug in chave_identificada)
            for nome in preferencias
        ):
            return identificado
    return _nome_cadastrado(cadastro) or atual or identificado


def construir_metadados_bula(
    texto: str,
    caminho_arquivo: str | Path,
    arquivo_id: str,
    bula_index: int,
    nome_atual: str = "",
    cadastro: dict[str, Any] | None = None,
) -> dict[str, str | int | bool]:
    """Cria metadados auditáveis e compatíveis com o armazenamento Chroma."""
    caminho = Path(caminho_arquivo)
    cadastro = cadastro if cadastro is not None else carregar_cadastro_download(caminho)
    resultado_download = cadastro.get("resultado") or {}

    nome_comercial = resolver_nome_comercial(texto, cadastro, nome_atual)
    principio_fallback = _valor_textual(cadastro.get("principal"))
    principio_ativo = identificar_principio_ativo(
        texto,
        nome_comercial,
        principio_fallback,
    )
    forma = identificar_forma_farmaceutica(texto)
    concentracao = identificar_concentracao(texto)
    via = identificar_via_administracao(texto)
    fabricante = identificar_fabricante(texto)
    tipo_bula = identificar_tipo_bula(texto, caminho.name)
    versao_bula, data_bula = identificar_versao_data(texto)
    numero_registro = _valor_textual(resultado_download.get("numeroRegistro"))
    aliases = _aliases_unicos(
        nome_comercial,
        principio_ativo,
        cadastro.get("principal"),
        cadastro.get("termosBusca") or [],
        resultado_download.get("nomeEncontrado"),
    )

    chave_registro = numero_registro or normalizar_nome_medicamento(caminho.stem)
    medicamento_id = "med_" + sha256(
        f"{chave_registro}|{normalizar_nome_medicamento(nome_comercial)}".encode("utf-8")
    ).hexdigest()[:24]
    bula_id = "bula_" + sha256(
        (
            f"{medicamento_id}|{normalizar_nome_medicamento(forma)}|"
            f"{normalizar_nome_medicamento(concentracao)}|{tipo_bula}|{bula_index}"
        ).encode("utf-8")
    ).hexdigest()[:24]
    fonte_url = _valor_textual(
        resultado_download.get("urlProfissional")
        or resultado_download.get("url")
    )
    arquivado_nome = f"{caminho.stem}-{arquivo_id[:12]}.pdf"

    return {
        "metadata_schema_version": VERSAO_ESQUEMA_METADADOS,
        "medicamento_id": medicamento_id,
        "bula_id": bula_id,
        "nome_comercial": nome_comercial,
        "principio_ativo": principio_ativo,
        "aliases_json": json.dumps(aliases, ensure_ascii=False),
        "medicamento": nome_comercial,
        "medicamento_normalizado": normalizar_nome_medicamento(nome_comercial),
        "forma_farmaceutica": forma,
        "concentracao": concentracao,
        "via_administracao": via,
        "fabricante": fabricante,
        "numero_registro": numero_registro,
        "tipo_bula": tipo_bula,
        "versao_bula": versao_bula,
        "data_bula": data_bula,
        "fonte_oficial": "Bulário Eletrônico da Anvisa",
        "fonte_url": fonte_url,
        "source": caminho.as_posix(),
        "arquivo_id": arquivo_id,
        "arquivo_hash_sha256": arquivo_id,
        "arquivo_hash_confirmado": True,
        "arquivo_nome": caminho.name,
        "arquivo_arquivado_nome": arquivado_nome,
        "bula_index": bula_index,
        "data_indexacao": datetime.now(UTC).isoformat(timespec="seconds"),
    }
