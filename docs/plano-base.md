# Polaritics — Plano da base do projeto (MVP Câmara, 57ª legislatura)

> Referência de método: [metodologia.md](metodologia.md). Este plano cobre a parte de dados e cálculo. O site vem depois.

## 1. Stack (custo zero)

| Camada | Escolha | Por quê |
|---|---|---|
| Linguagem | Python 3.12 (gerenciado com `uv`) | Coleta, cálculo e modelo numa linguagem só. A versão 3.12 garante compatibilidade com JAX/NumPyro |
| Armazenamento analítico | Parquet + DuckDB (arquivo local) | Sem servidor, rápido, SQL, versionável por data de coleta |
| Modelo IRT | NumPyro (NUTS, MCMC) | Rápido em CPU para cerca de 600 deputados × 1.000 votações |
| Qualidade | `ruff`, `pytest`, checagens de sanidade dos dados | A publicação é bloqueada se algo falhar |
| Automação | GitHub Actions (cron semanal) | Gratuito; atualiza os dados e gera o relatório de validação |
| Saída | JSON/Parquet estáticos, consumidos depois por um site estático | Sem backend no MVP |

## 2. Estrutura do repositório

```
polaritics/
├── pyproject.toml
├── docs/                      metodologia.md, plano-base.md
├── src/polaritics/
│   ├── config.py              legislaturas, períodos de governo, versão da metodologia
│   ├── coleta/
│   │   ├── camara.py          arquivos em lote + API (paginação, retry, cache, manifesto com hash)
│   │   └── especialistas.py   notas de Bolognesi et al. (fonte original)
│   ├── base/
│   │   ├── esquema.sql        tabelas DuckDB (seção 3)
│   │   ├── partidos.py        siglas, fusões e sucessões (PROS→SOLIDARIEDADE, PTB+PATRIOTA→PRD, PSC→PODE…)
│   │   ├── bancadas.py        bloco/federação → partidos, por data
│   │   └── votacoes.py        nominal × simbólica, mérito × procedimento, codificação dos votos
│   ├── medidas/
│   │   ├── governismo.py      total e em votações disputadas, por ano e por tema
│   │   ├── fidelidade.py      alinhamento com a orientação do próprio partido ou bloco
│   │   └── ideologia/
│   │       ├── irt.py         modelo, âncoras, diagnósticos de convergência
│   │       ├── escala.py      transformação monotônica por partes para 0–10
│   │       └── faixas.py      7 faixas fixas e faixas cobertas pelo intervalo
│   ├── validacao/             critérios da seção 8 da metodologia → relatório
│   └── publicar/              exporta resultados versionados
├── data/                      (fora do git) raw/AAAA-MM-DD/, processed/, published/
└── tests/
```

## 3. Modelo de dados (DuckDB)

Pensado para receber o Senado, novas legislaturas e, no futuro, as câmaras municipais sem mudar a estrutura.

| Tabela | Campos principais | Observação |
|---|---|---|
| `pessoa` | id_pessoa, nome, id_tse, id_camara, id_senado | Identidade única entre casas e mandatos |
| `mandato` | id_pessoa, casa, legislatura, uf, inicio, fim, condicao | Titular ou suplente; períodos de exercício |
| `partido` | sigla, nome, sucessor, data_sucessao | Fusões e incorporações |
| `filiacao` | id_pessoa, partido, inicio, fim | Datada; derivada do partido registrado em cada voto |
| `governo` | esfera, chefe, partido, inicio, fim | Base para o governismo relativo ao período |
| `votacao` | id, casa, data, orgao, descricao, nominal, tipo (mérito ou procedimento), id_proposicao | |
| `voto` | id_votacao, id_pessoa, voto_original, voto_codificado, partido_na_data | O voto original nunca é sobrescrito |
| `orientacao` | id_votacao, bancada, orientacao | Inclui Governo, Oposição, Maioria e Minoria |
| `bancada_partido` | bancada, partido, inicio, fim | Liga a orientação de um bloco aos partidos que o compõem |
| `proposicao`, `proposicao_tema` | id, tipo, número, ano, ementa, temas | Base para os recortes temáticos |
| `nota_especialistas` | partido, nota, fonte, ano, regra_proxy | Âncora da escala |
| `resultado_*` | … + versao_metodologia, data_dados | Cada publicação fica congelada e reproduzível |

## 4. Etapas

| # | Etapa | Entregável | Pronto quando |
|---|---|---|---|
| M0 | Esqueleto | git, `uv`, `pyproject`, `ruff`, `pytest`, CI | CI verde com um teste trivial |
| M1 | Coleta da Câmara | Download dos arquivos em lote por legislatura (votações, votos, orientações, objetos, proposições, temas, deputados), cache e manifesto | Download idempotente; segunda execução não baixa nada; checagem "> 500 votações nominais" |
| M2 | Base normalizada | Esquema DuckDB carregado; partidos harmonizados; filiação datada; bancada→partido; classificador mérito × procedimento usando o tipo do objeto votado (REQ etc.) em vez de palavras-chave | Testes cobrindo fusões, troca de partido na janela de 2026 e blocos |
| M3 | Medidas simples | Governismo (total e disputado) e fidelidade | Média da Câmara a ≤ 3 p.p. do Radar do Congresso |
| M4 | Ideologia | IRT por MCMC (2+ cadeias), escala monotônica, faixas, intervalo de 90%, variante só com mérito | R-hat < 1,01; critérios da seção 8 da metodologia |
| M5 | Validação | Relatório automático (Markdown/HTML) com todos os critérios | O relatório decide se os resultados podem ser publicados |
| M6 | Exportação | JSON por deputado e por partido, com votações explicativas e links oficiais | Esquema documentado, pronto para o site |

## 5. Riscos já identificados nos testes

- **Nome de bloco truncado** nas orientações (ex.: `Bl UniPpFdrPsdbCid...`). É preciso mapear pela API de blocos da Câmara ou por uma tabela curada com datas. Fazer em M2.
- **Votações com erro 504 permanente** na API: usar os arquivos em lote como fonte principal e a API só como complemento.
- **Notas dos especialistas:** obter a base original dos autores e verificar a licença. Partidos fundidos depois do levantamento precisam de uma regra de proxy documentada.
- **Votos vazios** (887 registros com `voto` em branco): investigar em M2 antes de tratar como ausência.
