# Polaritics — Metodologia municipal (anexo)

> **Status:** m0.3 (nov/2026). Anexo da [metodologia](metodologia.md) para câmaras municipais. Vale tudo o que está lá, **exceto** o que este documento muda. Cada resultado municipal publicado indica a versão deste anexo (ex.: `m0.2`) e a da metodologia geral.
> Primeira câmara: **Franca-SP**.

## Por que um anexo

Uma análise exploratória com Franca (13/11/2026) mostrou que o modelo da Câmara dos Deputados funciona numa câmara municipal: o IRT converge e separa os vereadores pelo conteúdo das votações. Três peças, porém, dependem de coisas que o município não tem:

| Peça da metodologia geral | Por que não serve no município |
|---|---|
| Régua pelos dois maiores partidos-polo, cada um com ≥ 3 parlamentares (4.2) | Franca tem 15 vereadores. PT e PSOL têm 1 cada |
| Validação pela ordem dos partidos × especialistas (D7) | Com 1 ou 2 vereadores por partido, a mediana do partido é a de uma pessoa. Em 2024, 8 dos 15 vereadores trocaram de partido |
| Governismo pela orientação do Governo (5.2) | O SAPL não registra orientação de bancada nem liderança |

Também ficam de fora, por não terem sentido ou fonte no município: a visão "dentro do campo do partido", a fidelidade partidária, as referências externas (Pesquisa Legislativa Brasileira, GPS Partidário, Radar do Congresso) e os gastos da cota.

## M1. Fonte

- **SAPL** (Sistema de Apoio ao Processo Legislativo, Interlegis), API pública em `https://<câmara>/api/`. Franca: `sapl.franca.sp.leg.br`.
- Usados: legislaturas, vereadores, mandatos, filiações (com data), partidos, registros de votação, votos individuais, sessões plenárias e presenças, matérias (tipo, número, ementa) e autoria das matérias do chefe do Executivo.
- Cada arquivo baixado é registrado num manifesto com o hash SHA-256, como na Câmara.
- **Conferência:** o placar oficial de cada registro de votação tem de bater com a soma dos votos individuais. Em Franca bate em 3.603 de 3.604 registros. As divergências são listadas no relatório de validação.
- O SAPL é usado por centenas de câmaras municipais. Outra câmara entra pela configuração, sem mudar o código, desde que publique os votos individuais.
- **Siscam** (Sino Informática), para câmaras que migraram para ele. Franca passou a registrar as sessões no Siscam em maio de 2026, e o SAPL deixou de receber votações depois de 22/05/2026. **Cada período vem do sistema em que foi registrado:** o SAPL até a sua última votação, e o Siscam a partir do dia seguinte, para votações e presença. O cadastro (vereadores, mandatos, filiações, fotos) continua vindo do SAPL.
- **Por que não usar o histórico do Siscam:** ele também traz as votações de 2021 a maio de 2026, migradas do SAPL, mas com erros. Em 272 delas (22 com divergência), a votação aparece ligada a uma sessão anterior à data do próprio documento. Exemplo: o PL 226/2025, de dezembro de 2025, aparece votado na 3ª sessão ordinária de janeiro de 2025. Nenhum caso assim ocorre nos registros feitos diretamente no Siscam.
- **Coleta do Siscam:** não há API, e a exportação em CSV devolve erro. A coleta lê a listagem pública das votações nominais, que já traz os votos agrupados ("A Favor", "Contra", "Abstenções", "Não votaram"), e confere a contagem de cada grupo com a lista de nomes e o total de registros informado pela página.
- **Ligação entre as fontes:** o Siscam identifica o vereador por "Nome civil (Nome parlamentar)". O nome parlamentar é ligado ao cadastro do SAPL sem diferenciar maiúsculas nem acentos. Um nome sem correspondência interrompe a construção da base.

## M2. Unidade e período

- **Vereador → mandato → legislatura municipal.** Cada legislatura é estimada **separadamente**, com modelo e régua próprios. Franca: 11ª (2021–2024) e 12ª (2025–2028).
- A página do vereador mostra cada legislatura em que ele votou. Como a régua é recalibrada em cada uma, a comparação da nota entre legislaturas é **aproximada**. O que se compara com segurança é a posição dentro de cada câmara.
- **Partido do vereador na legislatura:** o da filiação vigente no último voto dele na legislatura (a mesma regra da Câmara). O histórico completo de filiações aparece na página.
- Partido extinto (fusão ou incorporação) usa a nota do sucessor, pelas regras de D5.

## M3. Seleção e codificação das votações

Entram:
- Todos os registros de votação com voto individual registrado (votações nominais em sessão plenária), **inclusive moções** *(decisão M-D2)*.
- Como na Câmara, ficam de fora as votações quase unânimes (minoria < 2,5%).
- Também como na Câmara, ficam de fora os registros duplicados da mesma votação. O Siscam de Franca repete algumas votações com ids diferentes e o mesmo documento, sessão, dia e votos. Fica só o primeiro registro. O SAPL não tem esse problema. Com 15 vereadores, isso quer dizer: entra toda votação com ao menos um voto divergente.

**Por que as moções entram:** em Franca, moções de apoio, repúdio e aplauso estão entre as votações que mais separam os vereadores. Exemplos: anistia aos condenados do 8 de janeiro, aplausos a deputados federais, repúdio a medidas do governo federal. Muitas tratam de **política nacional**, e não da cidade. Isso é declarado na página: a posição municipal mede como o vereador vota, inclusive quando a câmara se manifesta sobre temas nacionais.

| Voto registrado | Codificação |
|---|---|
| Sim | 1 |
| Não | 0 |
| Abstenção, "Não votou" (ausência ou presidente da sessão) | Ausente |

O SAPL não registra obstrução.

**Variante "só mérito":** exclui as votações de procedimento: requerimento de urgência, requerimento, ata e redação final. Pareceres, emendas, substitutivos, vetos e moções contam como mérito, porque decidem o conteúdo. Em particular, o parecer contrário decide o destino do projeto. A classificação usa o tipo da matéria no SAPL, sem ler o texto.

## M4. Posição pelos votos

- **Modelo:** o mesmo IRT bayesiano da seção 4.1, com as mesmas prioris e o mesmo diagnóstico.
- **Sinal:** fixado pelos grupos de partidos (abaixo de 4,5 × acima de 5,5), como na Câmara.
- **Piso:** o vereador com < 10% de participação nas votações selecionadas não recebe faixa.

### M4.1 Régua por grupos-polo *(decisão M-D3)*

A régua continua linear e fixada por dois pontos de referência, mas os pontos são **grupos**, não partidos:

- **Grupo da esquerda:** todos os vereadores de partidos com nota dos especialistas abaixo de 4,5. **Grupo da direita:** todos os de partidos acima de 5,5. Os de partidos entre 4,5 e 5,5, ou sem nota, não entram em nenhum grupo.
- **Ponto de cada grupo:** a mediana das posições dos seus vereadores (em cada amostra do modelo) recebe a média das notas dos seus partidos, ponderada pelo número de vereadores.
- Todos os vereadores, inclusive os dos grupos, são posicionados **só pelos votos**.

Por que grupos: o partido-polo da Câmara exige ≥ 3 parlamentares, e nenhum partido de esquerda tem isso em Franca. Ancorar num único vereador faria a escala inteira depender de uma pessoa. O grupo usa todos os vereadores com classificação de especialistas e não exige mínimo por partido.

Limitação declarada: quando um grupo tem um só vereador, a nota dele fica, por construção, perto da nota do partido. A página avisa: "é referência da régua; a comparação com o partido não é informativa".

Se uma legislatura não tiver vereador num dos grupos, ela não recebe escala 0–10. Nesse caso são publicados só a ordem e os grupos de votação (M4.2).

### M4.2 Grupos de votação e posição na câmara *(decisão M-D4)*

Com poucas votações divergentes, os intervalos de muitos vereadores se sobrepõem. Uma nota com duas casas decimais daria a falsa impressão de que todos são distinguíveis. Por isso a página mostra também:

- **Posição na câmara:** a ordem do vereador, da esquerda para a direita, com o intervalo de 90% (ex.: "entre o 3º e o 12º de 15").
- **Grupo de votação:** os vereadores são ordenados pela mediana da posição. Um novo grupo começa entre dois vizinhos quando a probabilidade a posteriori de o da direita estar de fato à direita do outro é ≥ 95%. Vereadores do mesmo grupo **votam de forma indistinguível** com os dados disponíveis. A página diz: "vota de forma indistinguível de N colegas".

A faixa e a zona de fronteira (4.3 e 4.3.1) continuam valendo, com o mesmo bootstrap.

## M5. Governismo municipal *(decisão M-D5)*

- **Definição:** percentual de votos Sim nas votações nominais de **matérias de autoria do chefe do Executivo** (projetos de lei ordinária e complementar, emendas à Lei Orgânica, projetos de decreto legislativo). Votar Sim no projeto do prefeito é acompanhar o governo.
- **Excluídos:** emendas, substitutivos, pareceres, vetos e requerimentos, mesmo quando ligados a projetos do Executivo. Neles, a direção do voto do governo não é determinável pelos dados sem ler cada caso: uma emenda pode ser do próprio governo, e o sentido do voto num veto depende de como a câmara redige a votação.
- **Dois números:** total, e só nas votações **disputadas** (com ao menos um voto Não), que é o número principal. Sem orientação da oposição, "disputada" é a votação em que alguém votou contra o projeto do prefeito.
- **Exibição:** a taxa aparece com ≥ 5 votações disputadas em que o vereador votou. Abaixo disso, a página mostra só a contagem ("acompanhou o prefeito em 3 de 4 votações disputadas").
- **Sempre relativo ao prefeito do período.** Franca: Alexandre Ferreira (MDB), 2021–2024 e 2025–2028.

## M6. Presença

- Sessões plenárias ordinárias e extraordinárias encerradas e com lista de presença registrada. No Siscam, que faz uma chamada no Expediente e outra na Ordem do Dia, está presente na sessão quem consta como presente em ao menos uma delas. Sessões sem nenhuma presença registrada ficam fora, porque a falta da lista não é falta do vereador.
- **Presença** = sessões com presença ÷ sessões realizadas durante o mandato do vereador na legislatura. Entra no cálculo quem tiver ≥ 20 sessões no período.

## M7. Validação (critério para publicar)

| Teste | Critério | Bloqueia? |
|---|---|---|
| Convergência MCMC | R-hat < 1,01 nos parâmetros dos vereadores | Sim |
| Volume de dados | ≥ 30 votações informativas na legislatura e variante | Sim |
| Régua disponível | Ao menos um vereador em cada grupo-polo (M4.1) | Sim, para a escala 0–10 |
| Sensibilidade: todas × só mérito | Correlação das posições ≥ 0,90 | Sim |
| Estabilidade da classificação exibida (bootstrap, 100 réplicas) | ≥ 90% dos vereadores com a faixa exibida cobrindo ≥ 80% das réplicas (mesmo critério de D8) | Sim |
| Vereador × partido (Spearman entre a nota pelos votos e a nota do partido) | Acompanhado | Não |
| Peso das moções (correlação com e sem moções) | Acompanhado | Não |
| Vereadores em zona de fronteira; número de grupos de votação | Acompanhado | Não |

**Por que sai a ordem dos partidos (D7):** a ordem de partidos com 1 ou 2 vereadores é a ordem de pessoas, e o sinal da escala já é fixado pelos grupos-polo, o que tornaria o teste circular. A coerência com os especialistas passa a ser acompanhada no nível do vereador, sem bloquear, pelo mesmo motivo de D7: a diferença entre "diz ser" e "vota como" é o que o projeto quer mostrar.

**Transparência:** estas regras foram escritas **depois** de uma análise exploratória dos dados de Franca (13/11/2026). Ela usou o modelo da Câmara sem régua e mostrou: 62 votações divergentes na 12ª legislatura e 105 na 11ª, R-hat 1,004, três agrupamentos (PT e PSOL; um bloco de 10 vereadores; dois vereadores do PL) e correlação de 0,92 no bootstrap. Para reduzir a margem de escolha depois de ver o resultado, todos os limites numéricos são os da metodologia geral. Os únicos novos são o volume mínimo (30), a regra dos grupos de votação (95%) e o mínimo de 5 votações disputadas para o governismo. Nenhum deles foi ajustado depois de rodar o pipeline formal.

## M8. Limitações declaradas

- **Quase tudo é unânime.** Em Franca, cerca de 97% das votações nominais não têm voto contrário. A posição se apoia em poucas dezenas de votações por legislatura, contra mais de mil na Câmara.
- A pauta, inclusive a das moções, é definida pela própria câmara. Temas que não chegam a voto nominal não entram.
- Os partidos têm pouca identidade no nível municipal, e as trocas na janela de 2024 foram muitas. A nota do partido é contexto, não verdade.
- Votações simbólicas não entram na posição (só servem para saber se um projeto foi aprovado, M9), e o trabalho nas comissões não aparece.

## M9. Atividade legislativa *(decisão M-D8)*

- **O que conta:** projetos de lei ordinária e complementar, de emenda à Lei Orgânica, de decreto legislativo e de resolução, apresentados na legislatura com o vereador como **primeiro autor**. É a mesma regra dos deputados (seção 11.4 da metodologia geral).
- **Fonte:** a lista de documentos do Siscam, desde 2021. Ao contrário das votações, a lista de projetos migrada para o Siscam é confiável: o número de projetos por ano bate com o do SAPL (2021 a 2025, com diferença de 2 projetos em 2023). E só o Siscam continua sendo atualizado.
- **Aprovado:** projeto com ao menos uma votação em plenário, nominal ou simbólica, cujo resultado foi de aprovação. A situação de tramitação do Siscam não serve, porque aparece em menos de 10% dos projetos. Conferência: no período em que existem os dois sistemas, o resultado bate com as votações do SAPL em 804 de 805 projetos da 11ª legislatura.
- **Denominações à parte:** projetos cuja ementa só dá nome a rua ou próprio público ("Denomina…") são mostrados separadamente entre os aprovados. Na 11ª legislatura de Franca, foram 22% dos aprovados.
- **Ficam de fora** indicações, requerimentos e moções. São milhares por ano, quantidade não é qualidade, e o campo de autor das indicações no Siscam às vezes traz quem as cadastrou, não quem as assina.

## M10. Viagens oficiais *(decisão M-D9)*

- **Custo:** empenhos de diárias (elemento 3.3.90.14) e de passagens e locomoção (3.3.90.33) da Câmara no Portal da Transparência do município (EddyData), menos as anulações de cada empenho. Cada empenho cita no histórico o processo de viagem ("PIV nº/ano"), e o custo de uma viagem é a soma dos empenhos do seu PIV. Inclui diárias e despesas de assessores e motoristas.
- **Quem viajou:** o processo de viagem (PIV) no Siscam. Os vereadores são identificados por três sinais: (1) a autoria completa do PIV ("Nome civil (Nome parlamentar)"); (2) os apelidos na ementa, cortada antes da lista de acompanhantes (assessores, servidores, motoristas), e só os apelidos que apontam para um único vereador da legislatura ("Bassi", "Tidy"; "Donizete" não, porque é também nome do meio de outro vereador); (3) o nome civil depois de "VER." no histórico dos empenhos.
- **Por vereador:** número de viagens e o custo delas **dividido igualmente entre os vereadores que viajaram juntos**. A página mostra também o custo total das viagens de que o vereador participou e a lista de viagens, com o destino e o motivo, e link para o processo.
- **Cobertura, publicada no relatório de validação:** na 11ª legislatura, 70% do gasto com viagens que têm PIV tem ao menos um vereador identificado; na 12ª, 94%. O restante são viagens só de servidores (ex.: o ouvidor) ou PIVs cuja ementa não traz os nomes. Empenhos sem PIV (como o pedágio eletrônico da frota) não entram na conta por vereador.

## M11. Estrutura da câmara: subsídio e assessores *(decisão M-D10)*

- **Fonte:** folha de pagamento da Câmara no EddyData, mês a mês.
- **O que é publicado:** só agregados da câmara: o subsídio dos vereadores, o número de assessores parlamentares e o custo bruto deles por mês.
- **Por que não "o gabinete de cada vereador":** a folha não informa o gabinete do assessor (todos estão no departamento "ASSESSORES"). A única ligação são os avisos de nomeação da câmara, que são incompletos (a nomeação em lote de 2025, por exemplo, não diz o gabinete) e não registram exonerações. Publicar a equipe de cada gabinete com esses dados daria números errados. Como cada vereador tem direito ao mesmo número de assessores (dois, desde 2025), com o mesmo salário, o custo do gabinete também não diferencia os vereadores.

## M12. Campanha eleitoral *(decisão M-D11)*

- **Fonte:** dados abertos do TSE (candidaturas e prestação de contas de candidatos), eleições de 2020 e 2024.
- **Ligação:** o candidato é ligado ao vereador pelo nome civil e, se não houver correspondência, pelo nome de urna. A campanha aparece na legislatura que começou depois da eleição, só para quem exerceu mandato nela.
- **O que é publicado:** receita total e por origem (Fundo Especial de Financiamento de Campanha, Fundo Partidário, recursos próprios, pessoas físicas, incluindo financiamento coletivo, e outros, como doações de outros candidatos e partidos com recursos não públicos) e despesa contratada. Nomes e CPF de doadores não são gravados.

## Decisões

| # | Decisão | Desde |
|---|---|---|
| M-D1 | Cada legislatura municipal é estimada separadamente; a página do vereador mostra todas em que ele votou (M2) | m0.1 |
| M-D2 | Moções entram na visão padrão (M3) | m0.1 |
| M-D3 | Régua por grupos-polo (M4.1) | m0.1 |
| M-D4 | Posição na câmara e grupos de votação ao lado da faixa (M4.2) | m0.1 |
| M-D5 | Governismo pelas matérias do Executivo (M5) | m0.1 |
| M-D6 | Validação própria, sem a ordem dos partidos (M7) | m0.1 |
| M-D7 | Câmara que migrou para o Siscam: cada período vem do sistema em que foi registrado (SAPL até a sua última votação, Siscam depois) (M1) | m0.2 |
| M-D8 | Atividade legislativa: projetos como primeiro autor, aprovados pelas votações, denominações à parte (M9) | m0.3 |
| M-D9 | Viagens: custo pelos empenhos do processo de viagem, dividido entre os vereadores que viajaram (M10) | m0.3 |
| M-D10 | Gabinetes não são publicados por vereador; só a estrutura agregada da câmara (M11) | m0.3 |
| M-D11 | Campanha pela prestação de contas do TSE (M12) | m0.3 |

## Histórico

| Versão | Data | Mudanças |
|---|---|---|
| m0.1 | 13/11/2026 | Primeira versão, com Franca-SP. |
| m0.2 | 13/11/2026 | Siscam como fonte depois da última votação do SAPL (M-D7). Nenhum critério mudou. Com os dados de maio a novembro de 2026, a 12ª legislatura de Franca passou de 62 para 74 votações informativas e passou a atender ao critério de estabilidade nas duas variantes (100% com todas as votações e 93,3% só com mérito; com o SAPL até maio, eram 80% e 80%). |
| m0.3 | 14/11/2026 | Atividade legislativa (M9), viagens oficiais (M10), estrutura da câmara (M11) e campanha (M12). Nenhum critério da posição mudou. |
