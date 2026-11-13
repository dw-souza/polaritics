# Polaritics

Mostra como parlamentares **votam** e onde esse comportamento os coloca na escala política, de "mais à esquerda" a "mais à direita". Ao lado da posição, mostra a classificação do partido feita por especialistas e o governismo do parlamentar.

- Usa somente dados oficiais: Câmara, Senado e TSE.
- Cada resultado aponta para as votações que o explicam.
- A metodologia é pública e versionada: [docs/metodologia.md](docs/metodologia.md).
- Projeto independente, sem vínculo partidário, construído com ajuda de inteligência artificial (código e análise). As decisões de método foram tomadas e revisadas por uma pessoa e estão registradas na metodologia.
- O plano de construção está em [docs/plano-base.md](docs/plano-base.md).
- Câmaras municipais (em teste, começando por Franca-SP) seguem um anexo da metodologia: [docs/metodologia-municipal.md](docs/metodologia-municipal.md).

## Desenvolvimento

```bash
uv sync --all-extras   # instala as dependências (inclusive as do modelo)
uv run pytest          # roda os testes
uv run ruff check .    # verifica o estilo do código
```

## Pipeline

Cada etapa lê o resultado da anterior. `base` recria do zero a base de dados (`data/processed/polaritics.duckdb`). Os resultados do modelo e da validação ficam em outro arquivo (`data/processed/modelo.duckdb`) e sobrevivem a isso. Se os votos não mudaram, dá para reconstruir a base, recalcular as `medidas` e `publicar` sem rodar o modelo de novo. Se mudaram, `publicar` recusa e pede para rodar `ideologia` e `validar`: o modelo guarda uma impressão digital (hash) dos votos que usou.

```bash
uv run polaritics coletar     # baixa os dados da Câmara e as notas dos especialistas (~20 s)
uv run polaritics base        # monta a base DuckDB em data/processed/ (~10 s)
uv run polaritics medidas     # governismo e fidelidade partidária (~5 s)
uv run polaritics ideologia   # posição ideológica por MCMC, duas variantes (~15 min)
uv run polaritics validar     # critérios de publicação + relatório em data/published/ (~7 min)
uv run polaritics publicar    # carrega no Postgres só o que foi aprovado (~5 s)
```

`publicar` lê a conexão direta (unpooled) do Neon da variável `POLARITICS_DATABASE_URL`, no ambiente ou num arquivo `.env` local. O `.env` fica fora do git.

A validação com a Pesquisa Legislativa Brasileira usa um arquivo baixado manualmente, porque o Dataverse exige cadastro (guestbook). O repositório guarda só o resumo por partido, em `dados/referencia/`, para a atualização automática. Veja `src/polaritics/coleta/bls.py`.

### Câmaras municipais

Os dados vêm da API do SAPL (Interlegis) de cada câmara, configurada em `src/polaritics/municipal/config.py`. Câmaras que migraram para o Siscam (caso de Franca) usam o SAPL até a sua última votação e, depois dela, as votações e a presença lidas das páginas públicas do Siscam. Como o modelo de uma câmara pequena roda em segundos, `calcular` recria a base e os resultados juntos, em `data/processed/municipal.duckdb`.

```bash
uv run polaritics municipal coletar     # SAPL e Siscam (~4 min em Franca; ~45 min na primeira vez ou com --forcar)
uv run polaritics municipal calcular    # base, posição, governismo, presença e validação (~1 min)
uv run polaritics municipal publicar    # carrega no Postgres, schema `municipal`
```

O relatório de validação de cada legislatura fica em `data/published/validacao-<município>-<legislatura>.md`.

### Atualização automática

O workflow [atualizar.yml](.github/workflows/atualizar.yml) roda o pipeline inteiro todo sábado às 06:00 (Brasília) e também pode ser disparado à mão, em *Actions → Atualização semanal → Run workflow*, com a opção de só calcular e validar, sem publicar. Ele precisa do secret `POLARITICS_DATABASE_URL` (conexão unpooled do Neon) nas configurações do repositório. O relatório de validação aparece no resumo da execução e fica guardado como artefato por 90 dias.

## Licenças

- **Código:** MIT. Veja [LICENSE](LICENSE).
- **Dados e resultados publicados pelo Polaritics:** CC BY 4.0. Veja [LICENSE-DADOS.md](LICENSE-DADOS.md).
