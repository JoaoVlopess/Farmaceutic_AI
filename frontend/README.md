# IA Bulária — frontend

Interface Angular para seleção do medicamento e conversa com o assistente de bulas.

## Executar localmente

```powershell
cd frontend
npm install
npm start
```

Acesse `http://localhost:4200`.

## Estado atual

- autocomplete por nome comercial ou princípio ativo;
- seleção da forma farmacêutica;
- tela responsiva de conversa;
- respostas simuladas, ainda sem chamada ao backend Python/RAG.

## Validar

```powershell
npm run build
npm test -- --watch=false --browsers=ChromeHeadless
```
