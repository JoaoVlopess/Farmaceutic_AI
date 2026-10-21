# Metadados e citações das bulas

## Identidade estável

O catálogo trabalha com duas chaves internas:

- `medicamento_id`: identifica o medicamento agrupado no autocomplete;
- `bula_id`: identifica uma apresentação/bula específica selecionada para a
  busca vetorial.

O texto visível no Angular não é usado como chave. O autocomplete pode localizar
um item por nome comercial, princípio ativo, alias ou número de registro, mas a
consulta envia os IDs internos ao backend.

## Metadados persistidos

Cada chunk recebe os campos:

- nome comercial, princípio ativo e aliases;
- forma farmacêutica, concentração e via de administração;
- fabricante e número de registro;
- tipo de bula (`paciente` ou `profissional`);
- versão e data da bula;
- nome do arquivo, hash SHA-256 e indicação se o hash foi confirmado no PDF;
- URL oficial, quando conhecida;
- seção, página física inicial/final e identificador do chunk.

Campos não encontrados ficam vazios. Isso evita apresentar cabeçalhos, versões
ou nomes de arquivo como se fossem dados farmacêuticos válidos.

## Migração do banco existente

Prévia, sem escrita e sem embeddings:

```powershell
python -m RAG.migrar_metadados
```

Aplicação, também sem recalcular embeddings:

```powershell
python -m RAG.migrar_metadados --aplicar
```

Antes de atualizar o Chroma, o comando cria um backup JSON em `db/backups`.

## Limite dos documentos antigos

A migração consegue corrigir e organizar os dados que já estavam nos chunks,
mas não reconstrói a página física de um PDF apagado. Para que a interface
mostre página e permita abrir a fonte, o PDF antigo deve ser recuperado e
reindexado pelo fluxo atual.

Novos PDFs processados por `python main.py` são movidos para
`bulas_processadas` após a confirmação dos chunks. Assim, ficam disponíveis
para auditoria sem serem processados novamente pelo monitor.
