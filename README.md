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

## Licenças

- **Código:** MIT. Veja [LICENSE](LICENSE).
- **Dados e resultados publicados pelo Polaritics:** CC BY 4.0. Veja [LICENSE-DADOS.md](LICENSE-DADOS.md).
