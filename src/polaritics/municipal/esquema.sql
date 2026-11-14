-- Base municipal do Polaritics (DuckDB). Ver docs/metodologia-municipal.md.
-- Todas as tabelas levam `municipio` (slug da configuração) e os ids originais do SAPL.

create table municipio (
    municipio   varchar primary key,
    nome        varchar not null,
    uf          varchar not null,
    sapl        varchar not null
);

create table legislatura (
    municipio   varchar not null,
    numero      integer not null,
    inicio      date not null,
    fim         date not null,
    primary key (municipio, numero)
);

create table prefeito (
    municipio         varchar not null,
    nome              varchar not null,
    partido_na_posse  varchar not null,
    inicio            date not null,
    fim               date not null
);

create table vereador (
    municipio       varchar not null,
    id_vereador     varchar not null,
    nome            varchar not null,
    nome_completo   varchar,
    sexo            varchar,
    foto_url        varchar,
    primary key (municipio, id_vereador)
);

create table mandato (
    municipio       varchar not null,
    id_vereador     varchar not null,
    legislatura     integer not null,
    inicio          date not null,
    fim             date not null,
    titular         boolean
);

create table filiacao (
    municipio         varchar not null,
    id_vereador       varchar not null,
    partido_original  varchar not null,            -- sigla como está no SAPL
    partido           varchar not null,            -- sigla dos especialistas/Câmara
    inicio            date not null,
    fim               date                         -- null = filiação vigente
);

create table materia (
    municipio       varchar not null,
    id_materia      varchar not null,
    titulo          varchar,                       -- ex.: "Moção de Apoio nº 6 de 2025"
    sigla_tipo      varchar,
    tipo            varchar,
    numero          integer,
    ano             integer,
    ementa          varchar,
    do_executivo    boolean not null,              -- algum autor é o chefe do Executivo
    primary key (municipio, id_materia)
);

create table votacao (
    municipio       varchar not null,
    id_votacao      varchar not null,
    data            date not null,
    legislatura     integer,
    id_materia      varchar,
    placar_sim      integer,
    placar_nao      integer,
    tipo            varchar not null,              -- merito | procedimento
    eh_mocao        boolean not null,
    url             varchar,                       -- página oficial da votação ou da matéria
    aprovada        boolean,                       -- resultado de aprovação (null = sem dado)
    primary key (municipio, id_votacao)
);

create table voto (
    municipio         varchar not null,
    id_votacao        varchar not null,
    id_vereador       varchar not null,
    voto_original     varchar,
    voto_codificado   tinyint,                     -- 1 Sim | 0 Não | null
    primary key (municipio, id_votacao, id_vereador)
);

create table sessao (
    municipio   varchar not null,
    id_sessao   varchar not null,
    data        date not null,
    tipo        varchar,
    primary key (municipio, id_sessao)
);

create table presenca (
    municipio     varchar not null,
    id_sessao     varchar not null,
    id_vereador   varchar not null
);

-- Projetos (PLO, PLC, PELOM, PDL, PR) apresentados, do Siscam (metodologia municipal, M9).
create table projeto (
    municipio       varchar not null,
    id_projeto      varchar not null,
    titulo          varchar not null,
    sigla_tipo      varchar,
    numero          integer,
    ano             integer,
    data            date,
    ementa          varchar,
    id_vereador     varchar,                       -- primeiro autor, se for vereador
    do_executivo    boolean not null,
    denominacao     boolean not null,              -- dá nome a rua ou próprio público
    aprovado        boolean not null,              -- alguma votação em plenário o aprovou
    url             varchar,
    primary key (municipio, id_projeto)
);

-- Viagens oficiais (M10): o processo de viagem (PIV) do Siscam diz quem viajou; os empenhos
-- de diárias e locomoção do EddyData dizem quanto custou.
create table viagem (
    municipio       varchar not null,
    numero          integer not null,              -- PIV nº/ano
    ano             integer not null,
    data            date,
    ementa          varchar,
    url             varchar,
    primary key (municipio, numero, ano)
);

create table viagem_vereador (
    municipio       varchar not null,
    numero          integer not null,
    ano             integer not null,
    id_vereador     varchar not null
);

create table despesa_viagem (
    municipio       varchar not null,
    id_empenho      varchar not null,
    numero_empenho  integer,
    data            date not null,
    especie         varchar not null,              -- EMO empenho | EOA anulação
    valor           double not null,
    despesa         varchar,
    piv_numero      integer,                       -- do histórico do empenho (EOA herda do EMO)
    piv_ano         integer
);

-- Folha da Câmara, só subsídio de vereadores e salário de assessores parlamentares.
create table folha (
    municipio       varchar not null,
    ano             integer not null,
    mes             integer not null,
    nome            varchar,
    cargo           varchar,
    calculo         varchar,                       -- FOLHA, FERIAS 1, 13º…
    valor_bruto     double not null
);

-- Campanha (M12): prestação de contas ao TSE de quem foi vereador na legislatura seguinte.
create table campanha (
    municipio       varchar not null,
    id_vereador     varchar not null,
    ano_eleicao     integer not null,
    partido         varchar,
    situacao        varchar,                       -- ELEITO POR QP | ELEITO POR MÉDIA | SUPLENTE…
    receita         double not null,
    fundo_especial  double not null,               -- FEFC (fundo eleitoral)
    fundo_partidario double not null,
    proprios        double not null,
    pessoas_fisicas double not null,               -- inclui financiamento coletivo
    outros          double not null,               -- partidos e candidatos com outros recursos
    despesa         double not null
);

create table nota_especialistas (
    partido         varchar primary key,
    nota            double not null,
    origem          varchar not null
);

-- Votações com voto individual e ao menos um voto registrado: base de todas as medidas.
create view votacao_valida as
select v.* from votacao v
where exists (select 1 from voto vt where vt.municipio = v.municipio
              and vt.id_votacao = v.id_votacao and vt.voto_codificado is not null);
