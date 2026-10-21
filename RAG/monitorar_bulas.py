"""Monitor sequencial de PDFs para ingestão contínua de bulas."""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from RAG.indexar_documento import ResultadoIndexacao, indexar_pdf


@dataclass
class _Observacao:
    tamanho: int
    modificado_ns: int
    repeticoes: int = 1


@dataclass
class _Falha:
    tentativas: int
    tentar_apos: float


def _hash_arquivo(caminho: Path) -> str:
    digest = sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def arquivar_pdf_confirmado(
    caminho_pdf: Path,
    pasta_monitorada: Path,
    pasta_arquivo: Path | None = None,
) -> Path:
    """Move um PDF confirmado para o arquivo auditável, fora da entrada."""
    pasta_resolvida = pasta_monitorada.resolve()
    arquivo_resolvido = caminho_pdf.resolve()

    if arquivo_resolvido.suffix.casefold() != ".pdf":
        raise ValueError("O arquivamento automático aceita somente arquivos PDF.")
    if not arquivo_resolvido.is_relative_to(pasta_resolvida):
        raise ValueError("O arquivo está fora da pasta monitorada e não será movido.")

    digest = _hash_arquivo(arquivo_resolvido)
    destino_base = (
        pasta_arquivo.resolve()
        if pasta_arquivo
        else (pasta_resolvida.parent / "bulas_processadas").resolve()
    )
    destino_base.mkdir(parents=True, exist_ok=True)
    destino = destino_base / f"{arquivo_resolvido.stem}-{digest[:12]}.pdf"

    if destino.exists():
        if _hash_arquivo(destino) != digest:
            raise FileExistsError(f"Já existe outro arquivo no destino: {destino}")
        arquivo_resolvido.unlink()
    else:
        shutil.move(str(arquivo_resolvido), str(destino))
    return destino


def processar_e_arquivar_pdf(
    caminho_pdf: Path,
    pasta_monitorada: Path,
    pasta_arquivo: Path | None = None,
) -> ResultadoIndexacao:
    """Indexa, confirma no Chroma e só então arquiva o PDF original."""
    resultado = indexar_pdf(caminho_pdf)
    arquivar_pdf_confirmado(caminho_pdf, pasta_monitorada, pasta_arquivo)
    return resultado


class MonitorDeBulas:
    """Observa uma pasta por polling e processa no máximo um PDF por ciclo."""

    def __init__(
        self,
        pasta: str | Path = "bulas_pdf",
        intervalo_segundos: float = 5.0,
        verificacoes_estabilidade: int = 2,
        espera_erro_segundos: float = 30.0,
        espera_erro_maxima_segundos: float = 15 * 60.0,
        pasta_arquivo: str | Path = "bulas_processadas",
    ) -> None:
        self.pasta = Path(pasta)
        self.pasta_arquivo = Path(pasta_arquivo)
        self.intervalo_segundos = intervalo_segundos
        self.verificacoes_estabilidade = max(2, verificacoes_estabilidade)
        self.espera_erro_segundos = espera_erro_segundos
        self.espera_erro_maxima_segundos = espera_erro_maxima_segundos
        self._observacoes: dict[Path, _Observacao] = {}
        self._falhas: dict[Path, _Falha] = {}
        self._pausa_global_ate = 0.0

    @staticmethod
    def _eh_erro_de_cota(erro: Exception) -> bool:
        mensagem = str(erro).casefold()
        return "resource_exhausted" in mensagem or "429" in mensagem

    @staticmethod
    def _espera_informada_pela_api(erro: Exception) -> float:
        mensagem = str(erro)
        correspondencias = re.findall(
            r"(?:retryDelay['\"]?\s*:\s*['\"]?|retry in\s+)(\d+(?:\.\d+)?)s",
            mensagem,
            flags=re.IGNORECASE,
        )
        return max((float(valor) for valor in correspondencias), default=0.0)

    def _pdfs(self) -> list[Path]:
        return sorted(
            (
                caminho
                for caminho in self.pasta.iterdir()
                if caminho.is_file() and caminho.suffix.casefold() == ".pdf"
            ),
            key=lambda caminho: caminho.name.casefold(),
        )

    def _esta_estavel(self, caminho: Path) -> bool:
        estado = caminho.stat()
        anterior = self._observacoes.get(caminho)
        if (
            anterior
            and anterior.tamanho == estado.st_size
            and anterior.modificado_ns == estado.st_mtime_ns
        ):
            anterior.repeticoes += 1
        else:
            self._observacoes[caminho] = _Observacao(
                tamanho=estado.st_size,
                modificado_ns=estado.st_mtime_ns,
            )
        return self._observacoes[caminho].repeticoes >= self.verificacoes_estabilidade

    def executar_ciclo(self) -> ResultadoIndexacao | None:
        """Processa sequencialmente o primeiro PDF estável e elegível."""
        self.pasta.mkdir(parents=True, exist_ok=True)
        agora = time.monotonic()
        if agora < self._pausa_global_ate:
            return None

        pdfs = self._pdfs()
        caminhos_atuais = set(pdfs)
        for caminho in set(self._observacoes) - caminhos_atuais:
            self._observacoes.pop(caminho, None)
            self._falhas.pop(caminho, None)

        for caminho in pdfs:
            falha = self._falhas.get(caminho)
            if falha and agora < falha.tentar_apos:
                continue
            if not self._esta_estavel(caminho):
                continue

            print(f"[INGESTÃO] Processando {caminho.name}...")
            try:
                resultado = processar_e_arquivar_pdf(
                    caminho,
                    self.pasta,
                    self.pasta_arquivo,
                )
            except Exception as erro:
                tentativas = (falha.tentativas if falha else 0) + 1
                espera_exponencial = min(
                    self.espera_erro_segundos * (2 ** (tentativas - 1)),
                    self.espera_erro_maxima_segundos,
                )
                espera = espera_exponencial
                if self._eh_erro_de_cota(erro):
                    espera_api = self._espera_informada_pela_api(erro)
                    espera = max(60.0, espera_api + 2.0, espera_exponencial)
                    self._pausa_global_ate = time.monotonic() + espera
                self._falhas[caminho] = _Falha(
                    tentativas=tentativas,
                    tentar_apos=time.monotonic() + espera,
                )
                print(
                    f"[ERRO] {caminho.name} foi mantido. "
                    f"Nova tentativa em {espera:.0f}s: {erro}"
                )
                return None

            self._observacoes.pop(caminho, None)
            self._falhas.pop(caminho, None)
            print(
                f"[OK] {caminho.name}: {resultado.quantidade_bulas} bula(s), "
                f"{resultado.quantidade_chunks} chunks confirmados. PDF arquivado."
            )
            return resultado
        return None

    def executar(self) -> None:
        """Mantém o monitor ativo até o usuário pressionar Ctrl+C."""
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.pasta_arquivo.mkdir(parents=True, exist_ok=True)
        print(f"Monitorando PDFs em: {self.pasta.resolve()}")
        print(f"Arquivo permanente em: {self.pasta_arquivo.resolve()}")
        print("Processamento sequencial ativo. Pressione Ctrl+C para encerrar.")
        try:
            while True:
                self.executar_ciclo()
                time.sleep(self.intervalo_segundos)
        except KeyboardInterrupt:
            print("\nMonitor encerrado pelo usuário.")


def monitorar_pasta(pasta: str | Path = "bulas_pdf") -> None:
    MonitorDeBulas(pasta=pasta).executar()
