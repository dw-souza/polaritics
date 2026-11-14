-- Publicação municipal no Postgres (Neon), separada do schema `publicado` da Câmara.
-- Cada carga substitui as linhas do município; o histórico fica em `publicacao`.

create schema if not exists municipal;

create table if not exists municipal.publicacao (
    id                  bigint primary key,
    municipio           text not null,
    legislatura         integer not null,
    versao_metodologia  text not null,     -- ex.: "0.3 + m0.1"
    variantes           text[] not null,   -- variantes da posição aprovadas (pode ser vazio)
    dados_ate           date not null,
    publicado_em        timestamptz not null
);

create table if not exists municipal.municipio (
    municipio   text primary key,
    nome        text not null,
    uf          text not null,
    sapl        text not null
);

create table if not exists municipal.legislatura (
    municipio           text not null,
    numero              integer not null,
    inicio              date not null,
    fim                 date not null,
    prefeito            text,
    partido_prefeito    text,
    n_votacoes          integer not null,  -- registros de votação com voto individual
    n_divergentes       integer not null,  -- com ao menos um voto na minoria
    primary key (municipio, numero)
);

create table if not exists municipal.vereador (
    municipio       text not null,
    id_vereador     text not null,
    nome            text not null,
    nome_completo   text,
    sexo            text,
    foto_url        text,
    primary key (municipio, id_vereador)
);

-- Uma linha por legislatura em que o vereador votou; partido = o do último voto (M2).
create table if not exists municipal.mandato (
    municipio       text not null,
    id_vereador     text not null,
    legislatura     integer not null,
    partido         text,
    n_votos         integer not null,
    primary key (municipio, id_vereador, legislatura)
);

create table if not exists municipal.filiacao (
    municipio       text not null,
    id_vereador     text not null,
    partido         text not null,
    inicio          date not null,
    fim             date
);

create table if not exists municipal.posicao (
    municipio       text not null,
    legislatura     integer not null,
    variante        text not null,         -- todas | merito
    id_vereador     text not null,
    partido         text,
    nota            double precision not null,
    nota_p05        double precision not null,
    nota_p95        double precision not null,
    faixa           text not null,
    faixa_exibida   text not null,         -- faixa, ou "Entre X e Y" na zona de fronteira
    fronteira       boolean not null,
    posicao         integer not null,      -- 1 = mais à esquerda
    posicao_p05     integer not null,
    posicao_p95     integer not null,
    n_vereadores    integer not null,
    grupo           integer not null,      -- grupo de votação (M4.2), 1 = mais à esquerda
    tamanho_grupo   integer not null,
    grupo_polo      text,                  -- esquerda | direita | null (M4.1)
    polo_unico      boolean not null,
    n_votos         integer not null,
    primary key (municipio, legislatura, variante, id_vereador)
);

create table if not exists municipal.governismo (
    municipio               text not null,
    legislatura             integer not null,
    id_vereador             text not null,
    prefeito                text not null,
    n_total                 integer not null,
    taxa_total              double precision,
    n_disputadas            integer not null,
    alinhados_disputadas    integer,
    taxa_disputadas         double precision,
    suficiente              boolean not null,
    primary key (municipio, legislatura, id_vereador, prefeito)
);

create table if not exists municipal.presenca (
    municipio       text not null,
    legislatura     integer not null,
    id_vereador     text not null,
    sessoes         integer not null,
    presentes       integer not null,
    taxa            double precision not null,
    suficiente      boolean not null,
    primary key (municipio, legislatura, id_vereador)
);

create table if not exists municipal.votacao_explicativa (
    municipio       text not null,
    legislatura     integer not null,
    variante        text not null,
    id_vereador     text not null,
    ordem           integer not null,
    id_votacao      text not null,
    data            date not null,
    materia         text,                  -- ex.: "Moção de Apoio nº 6 de 2025"
    ementa          text,
    tipo            text not null,         -- merito | procedimento
    voto            text not null,
    placar          text not null,         -- ex.: "12 × 2"
    peso            double precision not null,
    url             text,                  -- página oficial (SAPL ou Siscam)
    primary key (municipio, legislatura, variante, id_vereador, ordem)
);

create table if not exists municipal.validacao (
    municipio           text not null,
    legislatura         integer not null,
    criterio            text not null,
    variante            text,
    valor               double precision,
    meta                text not null,
    status              text not null,
    detalhe             text not null,
    obrigatorio         boolean not null,
    versao_metodologia  text not null,
    gerado_em           timestamp not null
);

-- Projetos apresentados como primeiro autor e aprovados em plenário (M9).
create table if not exists municipal.atividade (
    municipio               text not null,
    legislatura             integer not null,
    id_vereador             text not null,
    apresentados            integer not null,
    aprovados               integer not null,
    aprovados_denominacao   integer not null,      -- só dão nome a vias e próprios públicos
    primary key (municipio, legislatura, id_vereador)
);

create table if not exists municipal.projeto_aprovado (
    municipio       text not null,
    legislatura     integer not null,
    id_vereador     text not null,
    titulo          text not null,
    ementa          text,
    data            date,
    denominacao     boolean not null,
    url             text
);

-- Viagens oficiais (M10): custo líquido do processo de viagem (PIV), dividido entre os
-- vereadores que viajaram.
create table if not exists municipal.viagens (
    municipio           text not null,
    legislatura         integer not null,
    id_vereador         text not null,
    viagens             integer not null,
    custo_atribuido     double precision not null,
    custo_das_viagens   double precision not null,
    primary key (municipio, legislatura, id_vereador)
);

create table if not exists municipal.viagem (
    municipio       text not null,
    legislatura     integer not null,
    numero          integer not null,
    ano             integer not null,
    data            date,
    ementa          text,
    custo           double precision not null,
    n_vereadores    integer not null,
    url             text,
    primary key (municipio, numero, ano)
);

create table if not exists municipal.viagem_vereador (
    municipio       text not null,
    numero          integer not null,
    ano             integer not null,
    id_vereador     text not null
);

-- Gasto de viagens da câmara por ano: total, com vereador identificado e sem processo (PIV).
create table if not exists municipal.viagem_ano (
    municipio       text not null,
    ano             integer not null,
    total           double precision not null,
    com_vereador    double precision not null,
    sem_piv         double precision not null,
    primary key (municipio, ano)
);

-- Folha (M11): subsídio dos vereadores e número e custo dos assessores parlamentares.
create table if not exists municipal.folha_mes (
    municipio           text not null,
    ano                 integer not null,
    mes                 integer not null,
    vereadores          integer not null,
    subsidio            double precision,
    assessores          integer not null,
    custo_assessores    double precision,
    primary key (municipio, ano, mes)
);

-- Campanha (M12): prestação de contas ao TSE na eleição que levou ao mandato.
create table if not exists municipal.campanha (
    municipio           text not null,
    legislatura         integer not null,
    id_vereador         text not null,
    ano_eleicao         integer not null,
    partido             text,
    situacao            text,
    receita             double precision not null,
    fundo_especial      double precision not null,
    fundo_partidario    double precision not null,
    proprios            double precision not null,
    pessoas_fisicas     double precision not null,
    outros              double precision not null,
    despesa             double precision not null,
    primary key (municipio, legislatura, id_vereador)
);
