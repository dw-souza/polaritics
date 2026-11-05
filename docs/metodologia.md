# Polaritics — Metodologia

> **Status:** v0.2 (nov/2026). Nada é publicado sem passar pela validação da seção 8. O histórico de mudanças está no fim do documento.
> Toda mudança de metodologia é versionada; cada resultado publicado indica a versão da metodologia que o gerou.

## Objetivo

Permitir que o eleitor compare **o que o parlamentar diz ser** (o partido e o espectro com que se apresenta) com **o que ele faz** (como vota). Quem escolheu um candidato porque ele se diz de direita, de esquerda ou de centro deve conseguir verificar se o comportamento dele em plenário confirma isso, e quanto desse comportamento é apoio ou oposição ao governo do momento.

## 0. Princípios

1. **Só dados oficiais e primários** entram no cálculo. Imprensa e estudos externos servem para *contexto* e *validação*, nunca como insumo silencioso.
2. **Rastreabilidade total:** toda classificação aponta para as votações que a produziram, com link para a fonte oficial.
3. **Comportamento, não discurso:** medimos como o parlamentar *vota*, não o que ele declara.
4. **Incerteza sempre visível:** nenhuma posição é exibida sem intervalo de confiança e sem número mínimo de votos.
5. **Escala fixa, não relativa:** as faixas ("mais à esquerda" … "mais à direita") têm cortes fixos. Ninguém cai numa faixa da ponta só por estar na ponta do ranking.
6. **Três medidas separadas, nunca fundidas:** posição ideológica estimada, classificação do partido e governismo são números distintos e exibidos lado a lado (seção 5).
7. **Reprodutibilidade:** código, dados brutos congelados e parâmetros públicos; qualquer pessoa deve conseguir reproduzir os números.

## 1. Fontes

| Uso | Fonte | Observações |
|---|---|---|
| Votações nominais, votos individuais, orientações de bancada e do governo | API Dados Abertos da Câmara (`dadosabertos.camara.leg.br/api/v2`) + arquivos anuais em lote | Fonte principal do MVP |
| Idem, Senado | Dados Abertos do Senado (`legis.senado.leg.br/dadosabertos`) | Fase 2. **A verificar:** disponibilidade da orientação do governo por votação |
| Identidade, partido, candidaturas | TSE Dados Abertos | Chave de identidade entre mandatos e casas |
| Classificação ideológica dos partidos | Bolognesi, Ribeiro, Codato & Silva, *Database on the ideological classification of all Brazilian political parties (2018-2022)*, Harvard Dataverse, doi:10.7910/DVN/MFIXKW, licença CC0. Respostas individuais de especialistas, escala 0–10, onda de 2022 | Âncora externa da escala. Média calculada pelo projeto a partir das respostas; arquivo com hash fixado |
| Validação | Pesquisa Legislativa Brasileira (Power & Zucco, Harvard Dataverse, doi:10.7910/DVN/WM9IZ8, CC0; onda de 2021, posição dos partidos atribuída pelos parlamentares, escala 1–10), GPS Partidário 2026 (Folha), Radar do Congresso (Congresso em Foco) | Apenas para comparar resultados, nunca como insumo. A PLB exige cadastro (guestbook) para download: o arquivo é baixado à mão, com hash fixado |

Dados brutos são baixados, versionados por data de coleta e mantidos congelados para cada publicação.

## 2. Unidade de análise e período

- **Pessoa → mandato → período legislativo.** O MVP cobre a 57ª legislatura (01/02/2023 – 31/01/2027).
- Suplentes que exerceram o mandato entram com os votos do período em que estavam em exercício.
- A filiação partidária é **datada**: cada voto é atribuído ao partido do parlamentar *na data do voto* (importante por causa da janela partidária de 2026).
- O modelo de dados é parametrizado por legislatura; a 58ª (a partir de 01/02/2027) entra sem mudança de código.

## 3. Seleção de votações

Entram:
- Votações **nominais em plenário** com votos individuais registrados, **tanto de mérito quanto de procedimento** (requerimentos de urgência, adiamento, retirada de pauta, destaques etc.).

Por que as votações de procedimento entram: na prática, é com elas que o governo e a oposição aceleram, travam ou derrubam pautas. Elas revelam posição política e são essenciais para medir o governismo. Como carregam mais governismo do que as de mérito, publicamos também uma **variante só com votações de mérito** (seção 8). Se a faixa de um parlamentar muda entre as duas versões, isso é sinalizado na página dele.

Ficam de fora (e isso é declarado ao usuário):
- Votações simbólicas (sem registro individual).
- Votações secretas e eleições de pessoas (ex.: indicações ao TCU, CNJ e CNMP).
- Registros duplicados da mesma votação sob outro identificador. A Câmara às vezes repete a votação para cada proposição ligada a ela; os votos ficam só no registro principal, que é o usado.
- Votações "quase unânimes" (minoria < 2,5%), que não trazem informação sobre posição.

Codificação dos votos:

| Voto registrado | Codificação |
|---|---|
| Sim | 1 |
| Não | 0 |
| **Obstrução** | **0 (equivale a "Não")** |
| Abstenção, ausência, art. 17 (presidente da Casa) | Ausente (não penaliza nem favorece) |

**Regra da obstrução:** obstrução é uma posição política ativa. O parlamentar está em plenário e escolhe, de forma declarada, impedir ou atrasar a aprovação da matéria. Por isso, ela é tratada como voto **"Não"** em todas as medidas: na posição ideológica, no governismo e na fidelidade partidária. Na página do parlamentar, a obstrução aparece com o próprio nome ("Obstrução, contada como Não"), para que fique claro o que foi registrado oficialmente e como o sistema interpretou o voto.

## 4. Medida 1 — Posição ideológica estimada (por votações)

### 4.1 Modelo
- **IRT bayesiano unidimensional** (modelo de ponto ideal; padrão acadêmico, equivalente ao usado no Voteview e no GPS Partidário).
- Estimação por MCMC, ≥ 2 cadeias, com diagnóstico de convergência (R-hat < 1,01; ESS mínimo). Se não convergir, a publicação é bloqueada.
- **Identificação:** a escala é fixada padronizando as posições em cada amostra (média 0, desvio 1). O sinal é fixado em cada cadeia: deputados de partidos que os especialistas classificam abaixo de 4,5 ficam, em média, à esquerda dos classificados acima de 5,5. As cadeias partem do primeiro componente da decomposição em valores singulares (SVD) da matriz de votos, o que evita o modo espelhado. Nenhum deputado é escolhido à mão.
- **Prioris:** posição ~ N(0, 1); dificuldade da votação ~ N(0, 5); discriminação ~ N(0, 2,5).

### 4.2 Tradução para a escala 0–10: duas visões

As duas visões saem das **mesmas amostras do modelo**. Só muda a régua aplicada no fim, e cada uma responde a uma pergunta diferente.

**Visão principal — "Comportamento de voto"** *(decisão D4)*
- Pergunta: *pelo jeito que vota, onde este parlamentar está? Isso bate com o que o partido diz ser?*
- Régua linear fixada por **dois partidos de referência**: o maior partido com nota dos especialistas abaixo de 4,5 e o maior acima de 5,5. Na 57ª legislatura, são **PT** (2,68) e **PL** (8,80). Esses dois recebem a nota dos especialistas; todos os outros partidos e deputados se posicionam **só pelos votos**.
- É a régua que define a **faixa** exibida e permite comparar "partido classificado como X × vota como Y".
- Por que não ajustar a régua a todos os partidos: no teste, a regressão isotônica reproduziu quase exatamente a nota de cada partido (PODE 7,44 × 7,44; PP 8,15 × 8,15), o que anula a comparação. A reta ajustada a todos os partidos comprimia a esquerda (o PT caía em centro-esquerda) e punha 61 deputados no teto 10. Com os dois polos, são 14.

**Visão secundária — "Dentro do campo do partido"**
- Pergunta: *comparado ao próprio partido, este parlamentar é mais moderado ou mais radical?*
- Régua monotônica por partes (regressão isotônica ponderada pelo tamanho das bancadas): cada partido fica perto da própria nota de especialistas, e o deputado aparece à esquerda ou à direita dele.
- Exibida como **comparação com o partido** (ex.: "mais à direita que o próprio partido"), **não** como uma segunda faixa. Assim cada pessoa tem uma faixa só.

Em ambas, só entram como referência partidos com nota dos especialistas e ≥ 3 deputados. A posição de cada partido é a mediana dos seus deputados, em cada amostra.

### 4.2.1 Visões selecionáveis *(decisão D6)*

O leitor pode trocar a visão, mas sempre parte de uma **visão padrão fixa**. São duas escolhas independentes:

| Escolha | Opções | Pergunta |
|---|---|---|
| Régua | **Comportamento de voto** (padrão) · Dentro do campo do partido | Onde está pelos votos × comparado ao próprio partido |
| Votações | **Todas** (padrão) · Só mérito | Com ou sem as votações de andamento da pauta |

Regras:
- **A visão padrão não muda conforme o resultado.** Ela só muda numa nova versão da metodologia, com justificativa escrita. Nunca muda de forma automática, nem porque um indicador entrou ou saiu de uma meta.
- **A visão em uso aparece sempre junto do resultado**, inclusive em links e imagens compartilhadas. Um link compartilhado abre na visão padrão, salvo se a pessoa escolher outra de propósito. Isso evita que se divulgue só a visão mais conveniente.
- Cada opção tem uma explicação curta na própria tela (rascunho na seção 4.2).
- Quando a faixa do parlamentar muda entre as visões, a página avisa ("a faixa depende da visão escolhida").
- A reta ajustada a todos os partidos não é oferecida: não responde a uma pergunta diferente e confundiria o leitor.

**Texto didático para a tela (rascunho):**
> *Posição pelos votos:* calculada só com as votações nominais do plenário. A régua é calibrada por dois partidos de referência (PT e PL), e todos os demais aparecem onde os votos os colocam. Um partido classificado como direita por especialistas pode aparecer mais ao centro se vota frequentemente com partidos de centro.
>
> *Comparado ao próprio partido:* mostra se o parlamentar vota de forma mais moderada ou mais radical que os colegas de partido.
>
> *Governismo:* não é ideologia. Mostra o quanto ele acompanha o governo do momento nas votações em que governo e oposição discordaram.

### 4.3 Faixas (cortes fixos, herdados do instrumento dos especialistas)

| Nota 0–10 | Faixa |
|---|---|
| 0,00 – 1,50 | Mais à esquerda |
| 1,51 – 3,00 | Esquerda |
| 3,01 – 4,49 | Centro-esquerda |
| 4,50 – 5,50 | Centro |
| 5,51 – 7,00 | Centro-direita |
| 7,01 – 8,50 | Direita |
| 8,51 – 10,00 | Mais à direita |

Os cortes são os do levantamento de especialistas. No instrumento original, as faixas das pontas se chamam "extrema esquerda" e "extrema direita". Usamos "mais à esquerda" e "mais à direita", como faz o GPS Partidário da Folha, porque o termo descreve uma **posição relativa no comportamento de voto**, não um juízo sobre a pessoa ou o partido.

Exibição: a nota de 0 a 10 com o intervalo de 90%, e a faixa ou a zona de fronteira (4.3.1).

### 4.3.1 Zona de fronteira *(decisão D8, v0.2)*

Faixas são cortes fixos sobre uma escala contínua. Quem está muito perto de um corte pode trocar de rótulo com pequenas mudanças nas votações consideradas, mesmo com a nota numérica estável.

- **Regra:** em cada uma das 100 réplicas do bootstrap das votações (seção 8), o deputado recebe uma faixa. Se a faixa publicada aparece em **menos de 80%** das réplicas, ele é exibido em **zona de fronteira**, com as duas faixas: a publicada e a outra mais frequente nas réplicas.
- **Exemplo de tela:** "Posição pelos votos: 5,52 · *Entre centro e centro-direita*. Está na fronteira entre duas faixas; pequenas mudanças nas votações consideradas trocam o rótulo."
- **Por quê:** na 57ª legislatura, 99% dos deputados com rótulo instável estavam a menos de 0,3 ponto de um corte, a maioria no corte de 5,5, onde fica o centrão. Mostrar uma faixa única para eles daria uma precisão que os dados não sustentam.

### 4.4 Piso mínimo
- Deputado com < 10% de participação nas votações selecionadas: estimado, mas **não exibido** com faixa ("dados insuficientes").

## 5. Medida 2 e 3 — Classificação do partido e governismo

Este é o comparativo central do produto: **ideologia não é o mesmo que apoio ao governo**, e o sistema precisa mostrar isso explicitamente.

### 5.1 Classificação do partido (externa)
- Nota 0–10 e faixa do partido segundo o levantamento de especialistas mais recente.
- Partido sem nota (criado ou fundido após o levantamento): "sem classificação de especialistas", sem imputação.

### 5.2 Governismo
- **Definição:** percentual de votos do parlamentar iguais à orientação da liderança do governo, apenas em votações em que o governo orientou (exclui "liberado").
- Obstrução contra a orientação do governo conta como voto contrário; ausência não entra no denominador.
- **Sempre relativo ao governo do período.** Em 2023–2026 o governo é do PT; em outro mandato, governismo alto significa outra coisa. Governismo **nunca** é convertido em ideologia.
- Calculado também por ano e por tema, para mostrar mudanças de comportamento (ex.: partidos que deixam a base).
- **Exibição:** só para quem votou em ao menos 10% das votações orientadas do período (mesma regra da posição ideológica) e em ao menos 30 votações disputadas. Suplentes com passagem curta e deputados licenciados por muito tempo ficam como "dados insuficientes".
- **Dois números, e o principal é o segundo:**
  - **Governismo total:** todas as votações em que o governo orientou.
  - **Governismo em votações disputadas (número principal):** só as votações em que a orientação do Governo é diferente da orientação da Oposição. Votar "com o governo" numa pauta que a oposição também apoia não é apoio ao governo, é consenso. Exemplo: a PEC 18/2025 (Segurança Pública) teve 487 votos Sim contra 15 Não, com PT e PL votando juntos. No teste, o governismo do PL cai de 32% (total) para 5% (disputadas).

### 5.3 Fidelidade partidária
- **Definição (v0.1):** percentual de votos iguais ao da **maioria da bancada do próprio partido** naquela votação. O partido é o da data do voto. O próprio deputado é excluído do cálculo da maioria, e só contam bancadas com ao menos 3 deputados votando Sim ou Não.
- **Por que não pela orientação oficial do partido:** a Câmara publica muitas orientações por *bloco*, com nomes truncados (ex.: `Bl UniPpFdrPsdbCid...`). Ela também não publica o histórico de composição dos blocos, só os atuais. Ligar cada deputado à orientação certa exigiria uma tabela curada à mão. A maioria da bancada não depende de nenhuma curadoria e é uma medida usual na literatura.
- **Futuro:** a fidelidade à orientação oficial pode ser adicionada quando houver uma tabela bloco → partidos documentada e com datas.

### 5.4 Como os três se combinam na página do parlamentar

```
Posição por votações (Polaritics) ●──────────── Centro-direita  [6,1 | IC 5,4–6,8]
Classificação do partido (especialistas) ●───── Direita         [7,6]
Governismo (governo Lula, 2023–2026) ●───────── 58%
Fidelidade ao partido ●──────────────────────── 81%
```

Leituras que o produto deve destacar, sem julgamento:
- **Deputado mais ao centro que o partido** (ou mais extremo).
- **Governismo incompatível com a faixa**: ex. deputado de direita com governismo alto. Possíveis explicações (cargos, pauta regional, votações consensuais) são apresentadas como hipóteses, não conclusões.

### 5.5 Separando ideologia de governo
No Brasil, a primeira dimensão das votações tende a misturar ideologia e governo × oposição (Zucco 2009; Zucco & Lauderdale 2011). No GPS Partidário 2026 a Folha observa o mesmo: "quanto mais o parlamentar vota com o governo, mais alinhado à esquerda". Mitigações, em ordem de implementação:
1. **v0.1:** exibir governismo ao lado da posição, deixando o leitor ver a correlação.
2. **v0.2:** estimar em paralelo um modelo **bidimensional** e reportar quanto da posição de cada um é explicado por governo × oposição.
3. **v0.3:** comparar com a legislatura anterior (governo Bolsonaro, 2019–2022). Uma dimensão que inverte quando o governo muda é governismo; uma que se mantém é ideologia. **É o teste mais forte e só exige dados que já existem.**

### 5.6 Pautas "cruzadas": quem propõe é de um lado, o conteúdo é do outro

Caso típico: um governo de esquerda prioriza uma pauta de segurança pública, área historicamente associada à direita.

**Como cada medida lida com isso:**

| Medida | Comportamento |
|---|---|
| Posição ideológica (IRT) | **Não depende do autor da pauta.** O modelo não sabe quem propôs nem lê o conteúdo. Ele aprende a direção de cada votação pelo *padrão* de quem vota junto. Se esquerda e direita votam Sim juntas, a votação quase não informa nada e pesa pouco (ou é removida, se a minoria for < 2,5%). Um deputado de direita que vota a favor não "anda para a esquerda" por isso. |
| Governismo total | Sobe para todos que votaram com o governo, inclusive a oposição. Por isso não é o número principal. |
| Governismo em votações disputadas | Ignora a votação se governo e oposição orientaram igual. Mede apoio ao governo onde houve conflito de fato. |

**Fase 3: classificação do conteúdo da pauta.** O IRT diz *quem vota junto com quem*, mas não diz *o que* foi votado. Para dizer "esta pauta tem conteúdo associado à direita", será necessária uma camada separada:
- Um **codebook público** por tema, com critérios do tipo "endurecimento penal → direita; desencarceramento → esquerda", inspirado em esquemas acadêmicos de codificação de agendas e programas.
- Classificação do texto oficial (ementa e inteiro teor) com apoio de LLM e **revisão humana obrigatória**, publicada votação a votação.
- Essa camada **não altera a posição IRT**. Ela gera indicadores próprios, como "votou a favor de X% das pautas de conteúdo à direita", e permite analisar o **Executivo** pelo conteúdo do que ele propõe, independentemente do partido do presidente.

## 6. Explicabilidade

Para cada parlamentar:
- **Votações que mais pesaram** na sua posição (maior discriminação do item × divergência em relação à mediana), cada uma com ementa, voto, orientação do partido, orientação do governo e link oficial.
- Contagem de votações consideradas, ausências e votos excluídos.
- Versão da metodologia e data dos dados.

## 7. Recortes temáticos (fase 3)

- Usar os temas oficiais das proposições (Câmara: `/proposicoes/{id}/temas`) para agrupar votações em: economia, costumes e valores, segurança pública, meio ambiente, direitos sociais.
- Estimar a posição por tema apenas onde houver votações suficientes; se não houver, mostrar "sem dados suficientes".

## 8. Validação (critério para publicar)

| Teste | Critério de aceitação (v0.1) |
|---|---|
| Ordem das medianas partidárias × especialistas (Spearman) | ≥ 0,80 *(decisão D7)* |
| Ordem das medianas partidárias × Pesquisa Legislativa Brasileira (Spearman) | ≥ 0,75. **Não bloqueia** a publicação *(decisão D9)* |
| Ordem dos partidos comparada ao GPS Partidário 2026 (votações) | Sem inversões entre famílias esquerda/centro/direita sem explicação documentada |
| Governismo médio da Câmara comparado ao Radar do Congresso | Diferença ≤ 3 p.p. ou explicada pela regra de codificação |
| Sensibilidade: todas as votações × só mérito | Correlação das posições individuais ≥ 0,90; parlamentares que mudam de faixa são listados e sinalizados |
| Estabilidade da classificação exibida (bootstrap por votação, 100 réplicas) | ≥ 90% dos deputados com a classificação exibida (faixa única ou par de fronteira, 4.3.1) cobrindo ≥ 80% das réplicas *(decisão D8)* |
| Convergência MCMC | R-hat < 1,01 em todos os parâmetros de deputados |

**Indicador acompanhado, sem efeito sobre a publicação:** a correlação de Pearson entre as medianas partidárias pelos votos e as notas dos especialistas. Ela mede o quanto as *distâncias* do comportamento de voto se parecem com a classificação dos especialistas, e é publicada a cada atualização. Na 57ª legislatura (até out/2026), o valor é 0,81. Uma subida ou queda é um **achado** (ex.: o centrão votando mais como a oposição), não um motivo para mudar o método.

Por que a ordem barra a publicação e a distância não *(D7)*: esperamos que a ordem dos partidos pelos votos seja coerente com a dos especialistas. As distâncias, não; a diferença entre "diz ser" e "vota como" é justamente o que o projeto quer mostrar. Exigir Pearson ≥ 0,85 (critério da v0.1 original) puniria o próprio achado.

**Indicador acompanhado, sem efeito sobre a publicação:** a fração de deputados em zona de fronteira. O critério de estabilidade da v0.2 só reprova quem oscila entre três ou mais faixas; o quanto o rótulo é frágil aparece neste indicador. Na 57ª legislatura: 16,3% (todas as votações) e 23,0% (só mérito). Um teto, se houver, será definido **antes** de rodar a 58ª legislatura, para não repetir o problema de escolher a regra depois de ver o resultado.

Sobre o bootstrap: reestimar por MCMC em cada réplica custaria horas. Cada réplica usa a moda a posteriori (MAP) do mesmo modelo, que nesta base tem correlação de 0,9999 com a mediana do MCMC e dá a mesma faixa para 97% dos deputados.

Transparência sobre D8: na v0.1, o critério exigia que ≥ 90% dos deputados mantivessem a **faixa única** em ≥ 80% das réplicas. Ele **reprovou** (83,7% com todas as votações; 77,0% só com mérito). A análise mostrou efeito de fronteira, não instabilidade do modelo (4.3.1). A v0.2 mudou a forma de exibir esses deputados e, com ela, o critério. Os valores do critério antigo continuam no relatório de validação.

Transparência: o critério D7 foi definido **depois** da primeira rodada completa do modelo (Spearman 0,89 com todas as votações e 0,91 só com mérito; Pearson 0,81 e 0,83). A partir desta versão, ele fica fixo, e qualquer mudança exige nova versão da metodologia.

## 9. Decisões

### Tomadas

| # | Decisão | Desde |
|---|---|---|
| D1 | Obstrução = "Não" em todas as medidas (seção 3) | v0.1 |
| D2 | Votações de procedimento entram, com variante de sensibilidade só com mérito (seções 3 e 8) | v0.1 |
| D3 | Faixas das pontas: "mais à esquerda" e "mais à direita" (seção 4.3) | v0.1 |
| D4 | Duas visões sobre as mesmas amostras: régua por dois partidos-polo (principal, define a faixa) e régua isotônica (comparação com o próprio partido) (seção 4.2) | v0.1 |
| D6 | Visões selecionáveis (régua × votações) com visão padrão fixa: comportamento de voto + todas as votações (seção 4.2.1) | v0.1 |
| D7 | Critério de publicação pela ordem dos partidos (Spearman); Pearson vira indicador acompanhado (seção 8) | v0.1 |
| D8 | Zona de fronteira: faixa instável no bootstrap é exibida como par de faixas; critério de estabilidade passa a avaliar a classificação exibida (seções 4.3.1 e 8) | v0.2 |
| D9 | Pesquisa Legislativa Brasileira como validação que não bloqueia: o download exige cadastro manual e não pode fazer parte da atualização automática. Mínimo de 10 respostas por partido; União = média de DEM e PSL; PRD sem nota (o Patriota não está na pesquisa) | v0.2 |
| D5 | Âncora: base original de Bolognesi et al. (onda 2022, Harvard Dataverse, CC0), com hash fixado. Incorporação mantém a nota do partido incorporador; fusão recebe a média dos partidos de origem (PRD = média de PTB e Patriota) | v0.1 |

### Em aberto

1. **Atualização da âncora:** adotar a 10ª onda da Pesquisa Legislativa Brasileira (2025) quando os dados forem publicados?
2. **Senado:** escala separada ou ponte com a Câmara via notas dos partidos?
3. **Partidos sem nota** (ex.: MISSÃO, criado em 2025): ficam posicionados pelos votos, sem comparação com especialistas, até a próxima onda.

## 10. Limitações declaradas

- Mede comportamento em votações nominais, não ideologia declarada nem atuação fora do plenário.
- A disciplina partidária é alta (no GPS Partidário 2026, 91,5% dos votos seguiram a orientação do líder); a variação individual é pequena e a incerteza importa.
- A agenda é definida pela presidência da Casa: temas não votados não entram.
- A âncora depende de um levantamento de especialistas; é uma escolha explícita e substituível.

## Anexo A — Teste exploratório (04/11/2026)

Dados: arquivos em lote da Câmara, 2023–2026 (até jun/2026). Modelo: IRT 1D estimado por MAP, uma aproximação rápida; o modelo final será por MCMC.

| Item | Resultado |
|---|---|
| Votações nominais de plenário com votos individuais | 1.121 (1.032 após remover as quase unânimes) |
| Votações com orientação do Governo | 873 |
| Deputados estimados (≥ 10% de participação) | 565 (mesmo número do GPS Partidário) |
| Governismo médio da Câmara | 71,6% (Radar do Congresso: 72%) |
| Governismo médio em votações disputadas (549 votações) | 61,9%; PL: 32,3% → 5,4%; NOVO: 24,6% → 4,6%; PT: 98,0% → 99,1% |
| Correlação das medianas partidárias com especialistas | Spearman 0,90; Pearson 0,80 |
| Variante "obstrução como ausência" | correlação 0,999 com a principal; 14/565 mudam de faixa |
| Variante "só mérito" | correlação 0,988; aproxima-se mais dos especialistas (Pearson 0,86); 78/564 mudam de faixa |

Leituras:
- A ordem dos partidos é coerente com os especialistas. Os deputados das pontas coincidem com os do GPS Partidário.
- Partidos do centrão com ministérios (PP, UNIÃO, REPUBLICANOS, PODE) aparecem como centro-direita pelos votos, e não como direita, que é a classificação dos especialistas. O governismo deles fica entre 78% e 80%. É exatamente o efeito governo × ideologia da seção 5.5.
- A decisão D1 (obstrução = Não) quase não altera o resultado. A decisão D2 (incluir procedimentos) altera mais, o que justifica manter a variante só com mérito sempre visível.

## Anexo B — Validação do governismo e da fidelidade (M3, 04/11/2026)

Dados: Câmara, 57ª legislatura, até out/2026. Cálculo pelo código do projeto (`polaritics medidas`).

| Teste | Resultado | Referência |
|---|---|---|
| Governismo médio da Câmara, 2023–2024 | 74,1% | Radar do Congresso: 72%. Diferença de 2,1 p.p., dentro do critério de ≤ 3 p.p. da seção 8 |
| Governismo médio, legislatura inteira | 71,7% total; 62,1% em votações disputadas | — |
| Caroline de Toni (PL-SC), votos contra o governo | 75,5% (legislatura até out/2026) | Radar do Congresso: 72% "desde fevereiro de 2023", com data de corte diferente |
| Deputados com dados suficientes | 565 | Igual ao número estimado pelo GPS Partidário (Folha) e pelo teste do anexo A |
| Fidelidade mediana por partido | 79,9% (PRD) a 99,0% (NOVO) | GPS Partidário: 91,5% dos votos seguem a orientação do líder |

Diferenças prováveis em relação ao Radar do Congresso: tratamento da obstrução, das abstenções e do período coberto. O Radar não publica essas regras com o mesmo detalhe.

## Histórico de versões

| Versão | Data | Mudanças |
|---|---|---|
| 0.1 | 04/11/2026 | Primeira versão completa (decisões D1–D7). |
| 0.2 | 04–05/11/2026 | Zona de fronteira e novo critério de estabilidade (D8), depois da reprovação do critério de faixa única. Validação com a Pesquisa Legislativa Brasileira (D9): Spearman 0,896 (todas as votações) e 0,907 (só mérito), 15 partidos. |

## Referências

- Bolognesi, B.; Ribeiro, E.; Codato, A. (2023). Uma nova classificação ideológica dos partidos políticos brasileiros. *Dados*, 66(2). https://doi.org/10.1590/dados.2023.66.2.303
- Bolognesi, B.; Ribeiro, E.; Codato, A.; Silva, B. F. O desaparecimento do centro ideológico no sistema partidário brasileiro. *Opinião Pública* (Unicamp).
- Power, T. J.; Zucco, C. (2023). Brazilian Legislative Surveys (Waves 1-9, 1990-2021). Harvard Dataverse, V1. https://doi.org/10.7910/DVN/WM9IZ8
- Zucco, C. (2009). Ideology or what? Legislative behavior in multiparty presidential settings. *Journal of Politics*.
- Zucco, C.; Lauderdale, B. (2011). Distinguishing between influences on Brazilian legislative behavior. *Legislative Studies Quarterly*.
- Folha de S.Paulo / DeltaFolha. GPS Partidário 2026. https://github.com/deltafolha/gps-partidario-2026
- Congresso em Foco. Radar do Congresso. https://radar.congressoemfoco.com.br
