"""Migra metadados legados do Chroma sem recalcular embeddings."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from RAG.banco_vetorial import obter_banco_vetorial
from utils import carregar_cadastro_download, construir_metadados_bula


def _hash_arquivo(caminho: Path) -> str:
    digest = sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _tipo_por_titulos(metadados: list[dict], tipo_atual: str) -> str:
    titulos = " ".join(
        str(metadata.get("section_title", "")).casefold()
        for metadata in metadados
    )
    if any(
        marcador in titulos
        for marcador in (
            "para que este medicamento",
            "como este medicamento funciona",
            "como devo usar este medicamento",
        )
    ):
        return "paciente"
    if any(
        marcador in titulos
        for marcador in ("indicações", "resultados de eficácia", "características farmacológicas")
    ):
        return "profissional"
    return tipo_atual


def preparar_migracao() -> tuple[list[str], list[dict], list[dict]]:
    """Retorna IDs, metadados novos e um resumo por bula."""
    banco = obter_banco_vetorial()
    dados = banco.get(include=["metadatas", "documents"])
    grupos: dict[tuple[str, int], list[int]] = defaultdict(list)
    for indice, metadata in enumerate(dados.get("metadatas", [])):
        source = str((metadata or {}).get("source", ""))
        bula_index = int((metadata or {}).get("bula_index", 1))
        grupos[(source, bula_index)].append(indice)

    ids_atualizados: list[str] = []
    metadados_atualizados: list[dict] = []
    resumo: list[dict] = []

    for (source, bula_index), indices in grupos.items():
        metadados_grupo = [dados["metadatas"][indice] or {} for indice in indices]
        documentos_grupo = [dados["documents"][indice] or "" for indice in indices]
        composicoes = [
            documento
            for documento, metadata in zip(documentos_grupo, metadados_grupo)
            if metadata.get("section_number") == 0
        ]
        texto_base = "\n\n".join(composicoes or documentos_grupo[:4])
        nomes = [
            str(metadata.get("medicamento", "")).strip()
            for metadata in metadados_grupo
            if metadata.get("medicamento")
        ]
        nome_atual = Counter(nomes).most_common(1)[0][0] if nomes else ""
        caminho = Path(source)
        cadastro = carregar_cadastro_download(caminho)

        arquivo_existente = caminho if caminho.exists() else None
        arquivo_id_existente = next(
            (
                str(metadata.get("arquivo_hash_sha256") or metadata.get("arquivo_id"))
                for metadata in metadados_grupo
                if metadata.get("arquivo_hash_sha256") or metadata.get("arquivo_id")
            ),
            "",
        )
        schema_atual = max(
            int(metadata.get("metadata_schema_version", 0) or 0)
            for metadata in metadados_grupo
        )
        if arquivo_existente:
            hash_confirmado = True
        elif schema_atual >= 2:
            # Em execuções idempotentes, não transforme o hash substituto
            # (calculado a partir do caminho) em hash confirmado do PDF.
            hash_confirmado = any(
                bool(metadata.get("arquivo_hash_confirmado"))
                for metadata in metadados_grupo
            )
        else:
            # A versão imediatamente anterior do indexador já salvava o hash
            # real em arquivo_id, mesmo sem o schema estruturado.
            hash_confirmado = bool(arquivo_id_existente)
        arquivo_id = (
            _hash_arquivo(arquivo_existente)
            if arquivo_existente
            else arquivo_id_existente or sha256(source.encode("utf-8")).hexdigest()
        )
        perfil = construir_metadados_bula(
            texto_base,
            caminho,
            arquivo_id,
            bula_index,
            nome_atual=nome_atual,
            cadastro=cadastro,
        )
        perfil["arquivo_hash_confirmado"] = hash_confirmado
        perfil["tipo_bula"] = _tipo_por_titulos(
            metadados_grupo,
            str(perfil["tipo_bula"]),
        )

        for indice in indices:
            ids_atualizados.append(dados["ids"][indice])
            metadados_atualizados.append({**dados["metadatas"][indice], **perfil})

        resumo.append(
            {
                "source": source,
                "bula_index": bula_index,
                "nome_anterior": nome_atual,
                "nome_comercial": perfil["nome_comercial"],
                "principio_ativo": perfil["principio_ativo"],
                "forma": perfil["forma_farmaceutica"],
                "concentracao": perfil["concentracao"],
                "tipo_bula": perfil["tipo_bula"],
                "numero_registro": perfil["numero_registro"],
            }
        )

    return ids_atualizados, metadados_atualizados, resumo


def migrar(aplicar: bool = False) -> list[dict]:
    ids, metadados, resumo = preparar_migracao()
    if not aplicar:
        return resumo

    pasta_backup = Path("db/backups")
    pasta_backup.mkdir(parents=True, exist_ok=True)
    instante = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = pasta_backup / f"metadados-antes-v2-{instante}.json"
    banco = obter_banco_vetorial()
    dados_anteriores = banco.get(include=["metadatas"])
    backup.write_text(
        json.dumps(
            {
                "ids": dados_anteriores.get("ids", []),
                "metadatas": dados_anteriores.get("metadatas", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    colecao = banco._collection
    for inicio in range(0, len(ids), 500):
        colecao.update(
            ids=ids[inicio : inicio + 500],
            metadatas=metadados[inicio : inicio + 500],
        )
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atualiza metadados do Chroma sem consumir embeddings."
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Efetiva as alterações. Sem esta opção, apenas mostra a prévia.",
    )
    argumentos = parser.parse_args()
    resumo = migrar(aplicar=argumentos.aplicar)
    alterados = [
        item for item in resumo if item["nome_anterior"] != item["nome_comercial"]
    ]
    print(
        f"{len(resumo)} bulas analisadas; {len(alterados)} nomes corrigidos; "
        f"modo={'APLICADO' if argumentos.aplicar else 'PRÉVIA'}."
    )
    for item in alterados:
        print(
            f"- {item['nome_anterior']} -> {item['nome_comercial']} "
            f"[{Path(item['source']).name}]"
        )


if __name__ == "__main__":
    main()
