import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Apresentacao {
  id: string;
  forma: string;
  concentracao: string;
  via_administracao: string;
  tipo_bula: string;
}

interface Medicamento {
  id: string;
  nome: string;
  nome_comercial: string;
  principio_ativo: string;
  aliases: string[];
  numero_registro: string;
  fabricante: string;
  apresentacoes: Apresentacao[];
}

interface FonteBula {
  indice: number;
  medicamento: string | null;
  principio_ativo: string | null;
  forma_farmaceutica: string | null;
  concentracao: string | null;
  secao_numero: number | null;
  secao_titulo: string | null;
  pagina: number | null;
  pagina_final: number | null;
  arquivo: string;
  arquivo_hash: string | null;
  chunk_id: string | null;
  numero_registro: string | null;
  versao_bula: string | null;
  data_bula: string | null;
  fonte_nome: string;
  fonte_url: string | null;
  trecho: string;
}

interface RespostaConsulta {
  resposta: string;
  fontes: FonteBula[];
}

interface Mensagem {
  autor: 'usuario' | 'assistente';
  texto: string;
  fontes?: FonteBula[];
  erro?: boolean;
}

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly http = inject(HttpClient);

  @ViewChild('messagesContainer')
  private messagesContainer?: ElementRef<HTMLDivElement>;

  protected readonly etapa = signal<'selecao' | 'chat'>('selecao');
  protected readonly termoBusca = signal('');
  protected readonly medicamentoSelecionado = signal<Medicamento | null>(null);
  protected readonly apresentacaoId = signal('');
  protected readonly listaAberta = signal(false);
  protected readonly mensagemAtual = signal('');
  protected readonly respondendo = signal(false);
  protected readonly carregandoMedicamentos = signal(true);
  protected readonly erroMedicamentos = signal('');
  protected readonly medicamentos = signal<Medicamento[]>([]);
  protected readonly mensagens = signal<Mensagem[]>([]);

  protected readonly apresentacaoSelecionada = computed(() =>
    this.medicamentoSelecionado()?.apresentacoes.find(
      (apresentacao) => apresentacao.id === this.apresentacaoId(),
    ) ?? null,
  );

  protected readonly sugestoes = [
    'Quais são as principais indicações?',
    'Quais são as contraindicações?',
    'Há interações medicamentosas importantes?',
  ];

  protected readonly medicamentosFiltrados = computed(() => {
    const termo = this.normalizar(this.termoBusca()).trim();
    if (termo.length < 2) return [];

    return this.medicamentos()
      .filter((medicamento) => {
        const campos = [
          medicamento.nome,
          medicamento.nome_comercial,
          medicamento.principio_ativo,
          medicamento.numero_registro,
          ...medicamento.aliases,
        ];
        return campos.some((campo) => this.normalizar(campo).includes(termo));
      })
      .slice(0, 8);
  });

  constructor() {
    this.carregarCatalogo();
  }

  protected selecionarMedicamento(medicamento: Medicamento): void {
    this.medicamentoSelecionado.set(medicamento);
    this.termoBusca.set(medicamento.nome);
    this.apresentacaoId.set(
      medicamento.apresentacoes.length === 1 ? medicamento.apresentacoes[0].id : '',
    );
    this.listaAberta.set(false);
  }

  protected atualizarBusca(valor: string): void {
    this.termoBusca.set(valor);
    this.medicamentoSelecionado.set(null);
    this.apresentacaoId.set('');
    this.listaAberta.set(true);
  }

  protected confirmarMedicamento(): void {
    const medicamento = this.medicamentoSelecionado();
    const apresentacao = this.apresentacaoSelecionada();
    if (!medicamento || !apresentacao) return;

    this.mensagens.set([
      {
        autor: 'assistente',
        texto: `Olá! Estou pronta para consultar a bula profissional de ${medicamento.nome}, ${this.rotuloApresentacao(apresentacao)}. O que você gostaria de saber?`,
      },
    ]);
    this.etapa.set('chat');
    this.rolarConversaParaBaixo();
  }

  protected trocarMedicamento(): void {
    this.etapa.set('selecao');
    this.mensagemAtual.set('');
    this.mensagens.set([]);
  }

  protected usarSugestao(sugestao: string): void {
    this.mensagemAtual.set(sugestao);
    this.enviarMensagem();
  }

  protected enviarMensagem(): void {
    const texto = this.mensagemAtual().trim();
    const medicamento = this.medicamentoSelecionado();
    const apresentacao = this.apresentacaoSelecionada();
    if (!texto || !medicamento || !apresentacao || this.respondendo()) return;

    this.mensagens.update((mensagens) => [...mensagens, { autor: 'usuario', texto }]);
    this.mensagemAtual.set('');
    this.respondendo.set(true);
    this.rolarConversaParaBaixo();

    this.http
      .post<RespostaConsulta>('/api/consultas', {
        medicamento_id: medicamento.id,
        bula_id: apresentacao.id,
        medicamento: medicamento.nome,
        forma_farmaceutica: apresentacao.forma,
        pergunta: texto,
      })
      .subscribe({
        next: (resultado) => {
          this.mensagens.update((mensagens) => [
            ...mensagens,
            { autor: 'assistente', texto: resultado.resposta, fontes: resultado.fontes },
          ]);
          this.respondendo.set(false);
          this.rolarConversaParaBaixo();
        },
        error: (erro: HttpErrorResponse) => {
          const detalhe =
            typeof erro.error?.detail === 'string'
              ? erro.error.detail
              : 'Não foi possível consultar a bula agora. Verifique se a API está em execução.';
          this.mensagens.update((mensagens) => [
            ...mensagens,
            { autor: 'assistente', texto: detalhe, erro: true },
          ]);
          this.respondendo.set(false);
          this.rolarConversaParaBaixo();
        },
      });
  }

  protected rotuloApresentacao(apresentacao: Apresentacao): string {
    return [apresentacao.forma, apresentacao.concentracao, apresentacao.via_administracao]
      .filter(Boolean)
      .join(' · ');
  }

  protected rotuloSecao(fonte: FonteBula): string {
    if (fonte.secao_numero === null || fonte.secao_numero === 0) {
      return fonte.secao_titulo || 'Apresentações e composição';
    }
    return `${fonte.secao_numero}. ${fonte.secao_titulo || 'Seção da bula'}`;
  }

  protected rotuloPagina(fonte: FonteBula): string {
    if (fonte.pagina === null) return 'Página disponível após reindexação';
    if (fonte.pagina_final && fonte.pagina_final !== fonte.pagina) {
      return `Páginas ${fonte.pagina}–${fonte.pagina_final}`;
    }
    return `Página ${fonte.pagina}`;
  }

  private carregarCatalogo(): void {
    this.http.get<Medicamento[]>('/api/medicamentos').subscribe({
      next: (medicamentos) => {
        this.medicamentos.set(medicamentos);
        this.carregandoMedicamentos.set(false);
      },
      error: () => {
        this.erroMedicamentos.set(
          'Não foi possível carregar os medicamentos. Confirme se a API está em execução.',
        );
        this.carregandoMedicamentos.set(false);
      },
    });
  }

  private normalizar(valor: string): string {
    return valor
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('pt-BR');
  }

  private rolarConversaParaBaixo(): void {
    setTimeout(() => {
      const elemento = this.messagesContainer?.nativeElement;
      elemento?.scrollTo({ top: elemento.scrollHeight, behavior: 'smooth' });
    });
  }
}
