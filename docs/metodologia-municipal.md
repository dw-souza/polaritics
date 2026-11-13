# Polaritics — Metodologia municipal (anexo)

> **Status:** m0.2 (nov/2026). Anexo da [metodologia](metodologia.md) para câmaras municipais. Vale tudo o que está lá, **exceto** o que este documento muda. Cada resultado municipal publicado indica a versão deste anexo (ex.: `m0.2`) e a da metodologia geral.
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
- Atividade legislativa e gastos ficam para uma versão futura. O SAPL não traz gastos, e a situação das matérias segue convenções próprias de cada câmara.

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
- Votações simbólicas e o trabalho nas comissões não aparecem.

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

## Histórico

| Versão | Data | Mudanças |
|---|---|---|
| m0.1 | 13/11/2026 | Primeira versão, com Franca-SP. |
| m0.2 | 13/11/2026 | Siscam como fonte depois da última votação do SAPL (M-D7). Nenhum critério mudou. Com os dados de maio a novembro de 2026, a 12ª legislatura de Franca passou de 62 para 74 votações informativas e passou a atender ao critério de estabilidade nas duas variantes (100% com todas as votações e 93,3% só com mérito; com o SAPL até maio, eram 80% e 80%). |
