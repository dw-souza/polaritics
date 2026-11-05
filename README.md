# Polaritics

Mostra como parlamentares **votam** e onde esse comportamento os coloca na escala política, de "mais à esquerda" a "mais à direita". Ao lado da posição, mostra a classificação do partido feita por especialistas e o governismo do parlamentar.

- Usa somente dados oficiais: Câmara, Senado e TSE.
- Cada resultado aponta para as votações que o explicam.
- A metodologia é pública e versionada: [docs/metodologia.md](docs/metodologia.md).
- O plano de construção está em [docs/plano-base.md](docs/plano-base.md).

## Desenvolvimento

```bash
uv sync --all-extras   # instala as dependências (inclusive as do modelo)
uv run pytest          # roda os testes
uv run ruff check .    # verifica o estilo do código
```

## Pipeline

Cada etapa lê o resultado da anterior. `base` recria a base local do zero; por isso, depois dela rode as etapas seguintes.

```bash
uv run polaritics coletar     # baixa os dados da Câmara e as notas dos especialistas (~20 s)
uv run polaritics base        # monta a base DuckDB em data/processed/ (~10 s)
uv run polaritics medidas     # governismo e fidelidade partidária (~5 s)
uv run polaritics ideologia   # posição ideológica por MCMC, duas variantes (~15 min)
uv run polaritics validar     # critérios de publicação + relatório em data/published/ (~7 min)
uv run polaritics publicar    # carrega no Postgres só o que foi aprovado (~5 s)
```

`publicar` lê a conexão direta (unpooled) do Neon da variável `POLARITICS_DATABASE_URL`, no ambiente ou num arquivo `.env` local. O `.env` fica fora do git.

A validação com a Pesquisa Legislativa Brasileira usa um arquivo baixado manualmente, porque o Dataverse exige cadastro (guestbook). Veja `src/polaritics/coleta/bls.py`.

## Licenças

- **Código:** MIT. Veja [LICENSE](LICENSE).
- **Dados e resultados publicados pelo Polaritics:** CC BY 4.0. Veja [LICENSE-DADOS.md](LICENSE-DADOS.md).
