import { CommonModule } from '@angular/common';
import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Medicamento {
  nome: string;
  principioAtivo: string;
  formas: string[];
}

interface Mensagem {
  autor: 'usuario' | 'assistente';
  texto: string;
}

const MEDICAMENTOS_INDEXADOS: Medicamento[] = [
  { nome: 'Paracetamol', principioAtivo: 'paracetamol', formas: ['Comprimido'] },
  { nome: 'Ibuprofeno', principioAtivo: 'ibuprofeno', formas: ['Cápsula'] },
  { nome: 'Dorflex', principioAtivo: 'dipirona + orfenadrina + cafeína', formas: ['Comprimido', 'Gotas'] },
  { nome: 'Dorflex Max', principioAtivo: 'dipirona + orfenadrina + cafeína', formas: ['Comprimido'] },
  { nome: 'Neosaldina', principioAtivo: 'dipirona + isometepteno + cafeína', formas: ['Comprimido'] },
  { nome: 'Torsilax', principioAtivo: 'diclofenaco + carisoprodol + paracetamol + cafeína', formas: ['Comprimido'] },
  { nome: 'Diclofenaco potássico', principioAtivo: 'diclofenaco potássico', formas: ['Comprimido'] },
  { nome: 'Diclofenaco sódico', principioAtivo: 'diclofenaco sódico', formas: ['Injetável'] },
  { nome: 'Naproxeno', principioAtivo: 'naproxeno', formas: ['Comprimido'] },
  { nome: 'Nimesulida', principioAtivo: 'nimesulida', formas: ['Comprimido'] },
  { nome: 'Meloxicam', principioAtivo: 'meloxicam', formas: ['Comprimido'] },
  { nome: 'Cetoprofeno', principioAtivo: 'cetoprofeno', formas: ['Cápsula'] },
  { nome: 'Tramadol', principioAtivo: 'cloridrato de tramadol', formas: ['Comprimido'] },
  { nome: 'Buscopan Composto', principioAtivo: 'escopolamina + dipirona', formas: ['Gotas'] },
  { nome: 'Tandrilax', principioAtivo: 'diclofenaco + carisoprodol + paracetamol + cafeína', formas: ['Comprimido'] },
  { nome: 'Etoricoxibe', principioAtivo: 'etoricoxibe', formas: ['Comprimido'] },
  { nome: 'Resfenol', principioAtivo: 'paracetamol + clorfeniramina + fenilefrina', formas: ['Cápsula'] },
  { nome: 'Loratadina', principioAtivo: 'loratadina', formas: ['Comprimido'] },
  { nome: 'Desloratadina', principioAtivo: 'desloratadina', formas: ['Xarope'] },
  { nome: 'Allegra', principioAtivo: 'fexofenadina', formas: ['Comprimido'] },
  { nome: 'Allegra Pediátrico', principioAtivo: 'fexofenadina', formas: ['Suspensão oral'] },
  { nome: 'Polaramine', principioAtivo: 'dexclorfeniramina', formas: ['Gotas'] },
  { nome: 'Hixizine', principioAtivo: 'hidroxizina', formas: ['Comprimido', 'Xarope'] },
  { nome: 'Strepsils', principioAtivo: 'amilmetacresol + álcool diclorobenzílico', formas: ['Pastilha'] },
];

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly etapa = signal<'selecao' | 'chat'>('selecao');
  protected readonly termoBusca = signal('');
  protected readonly medicamentoSelecionado = signal<Medicamento | null>(null);
  protected readonly formaSelecionada = signal('');
  protected readonly listaAberta = signal(false);
  protected readonly mensagemAtual = signal('');
  protected readonly respondendo = signal(false);
  protected readonly mensagens = signal<Mensagem[]>([]);

  protected readonly sugestoes = [
    'Quais são as principais indicações?',
    'Quais são as contraindicações?',
    'Há interações medicamentosas importantes?',
  ];

  protected readonly medicamentosFiltrados = computed(() => {
    const termo = this.normalizar(this.termoBusca()).trim();

    if (termo.length < 2) {
      return [];
    }

    return MEDICAMENTOS_INDEXADOS.filter((medicamento) => {
      const conteudo = this.normalizar(`${medicamento.nome} ${medicamento.principioAtivo}`);
      return conteudo.includes(termo);
    }).slice(0, 6);
  });

  protected selecionarMedicamento(medicamento: Medicamento): void {
    this.medicamentoSelecionado.set(medicamento);
    this.termoBusca.set(medicamento.nome);
    this.formaSelecionada.set(medicamento.formas.length === 1 ? medicamento.formas[0] : '');
    this.listaAberta.set(false);
  }

  protected atualizarBusca(valor: string): void {
    this.termoBusca.set(valor);
    this.medicamentoSelecionado.set(null);
    this.formaSelecionada.set('');
    this.listaAberta.set(true);
  }

  protected confirmarMedicamento(): void {
    const medicamento = this.medicamentoSelecionado();
    if (!medicamento || !this.formaSelecionada()) {
      return;
    }

    this.mensagens.set([
      {
        autor: 'assistente',
        texto: `Olá! Estou pronta para consultar a bula profissional de ${medicamento.nome} (${this.formaSelecionada()}). O que você gostaria de saber?`,
      },
    ]);
    this.etapa.set('chat');
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

    if (!texto || !medicamento || this.respondendo()) {
      return;
    }

    this.mensagens.update((mensagens) => [...mensagens, { autor: 'usuario', texto }]);
    this.mensagemAtual.set('');
    this.respondendo.set(true);

    window.setTimeout(() => {
      this.mensagens.update((mensagens) => [
        ...mensagens,
        {
          autor: 'assistente',
          texto: `Esta é uma prévia da interface. A pergunta sobre ${medicamento.nome} foi recebida; na próxima etapa, ela será enviada ao RAG e a resposta virá acompanhada dos trechos da bula utilizados.`,
        },
      ]);
      this.respondendo.set(false);
    }, 700);
  }

  private normalizar(valor: string): string {
    return valor
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('pt-BR');
  }
}
