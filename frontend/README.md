# Farmaceutic AI — frontend

Interface Angular para seleção do medicamento e conversa com o assistente de
bulas.

## Executar localmente

Em um terminal, inicie a API a partir da raiz do projeto:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn api:app --reload --port 8000
```

Em outro terminal, inicie o Angular:

```powershell
cd frontend
npm install
npm start
```

Acesse `http://localhost:4200`. O servidor de desenvolvimento encaminha `/api`
para `http://127.0.0.1:8000`.

## Fluxo conectado

- o catálogo é carregado diretamente dos metadados estruturados do Chroma;
- o autocomplete pesquisa nome comercial, princípio ativo, aliases e registro;
- a seleção envia `medicamento_id` e `bula_id`, sem depender do texto exibido;
- a pergunta do chat é enviada à API e transformada em embedding pelo RAG;
- o agente responde usando os chunks recuperados;
- as afirmações da resposta usam indicadores como `[1]` e `[2]`;
- cada evidência mostra trecho, seção, página, arquivo, versão/data e link da
  fonte quando ela está disponível.

## Metadados e PDFs antigos

Para visualizar uma prévia da correção dos metadados sem consumir embeddings:

```powershell
python -m RAG.migrar_metadados
```

Para aplicar a correção no Chroma existente:

```powershell
python -m RAG.migrar_metadados --aplicar
```

A migração atualiza somente metadados e cria um backup em `db/backups`. Ela não
consegue recuperar o número da página de PDFs já removidos. Esses documentos
precisam ser recuperados e reindexados. As novas ingestões guardam a página
física do PDF e arquivam a fonte em `bulas_processadas`, em vez de apagá-la.

## Validar

```powershell
npm run build
npm test -- --watch=false --browsers=ChromeHeadless
```
