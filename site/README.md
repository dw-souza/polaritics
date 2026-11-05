# Site do Polaritics

Next.js (App Router, Cache Components) que lê os resultados publicados no schema `publicado` do Postgres (Neon). Os dados vêm do pipeline em Python na raiz do repositório e mudam uma vez por semana. Cada consulta fica em cache por uma hora (`cacheLife("hours")`).

## Rodar localmente

```bash
cd site
npm install
# .env.local com a conexão POOLED do Neon (nunca a unpooled; o arquivo fica fora do git)
echo 'POLARITICS_DATABASE_URL_POOLED=postgresql://...-pooler...' > .env.local
npm run dev        # http://localhost:3000
npm run build      # a build consulta o banco para pré-renderizar as páginas estáticas
```

## Deploy na Vercel

1. Importe o repositório e defina **Root Directory = `site`**.
2. Em *Environment Variables*, crie `POLARITICS_DATABASE_URL_POOLED` com a string **pooled** do Neon, para Production e Preview. A build também precisa dela.
3. Depois da atualização de sábado, as páginas se renovam em até 1 hora.

## Páginas

- `/`: busca de deputados com a faixa de cada um.
- `/deputado/[id]`: régua 0–10, visões selecionáveis (`?regua=campo`, `?votacoes=merito`), comparação com o partido, governismo, fidelidade e votações que mais pesaram.
- `/partidos`: especialistas × votos por partido, em gráfico e tabela.
- `/metodologia`: resumo didático; o documento completo fica em `docs/metodologia.md`.

## Cores

A escala política usa roxo (esquerda) ↔ cinza (centro) ↔ laranja (direita), cores sem associação partidária no Brasil. Os tons foram gerados em OKLCH a partir da paleta de referência e validados como rampas ordinais nos temas claro e escuro (`app/globals.css`).
