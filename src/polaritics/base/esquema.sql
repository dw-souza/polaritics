-- Base normalizada do Polaritics (DuckDB). Ver docs/plano-base.md, seção 3.
-- Os campos *_original guardam o valor exatamente como veio da fonte.

create table legislatura (
    numero      integer primary key,
    inicio      date not null,
    fim         date not null
);

create table governo (
    esfera            varchar not null,
    chefe             varchar not null,
    partido_na_posse  varchar not null,
    inicio            date not null,
    fim               date not null
);

create table partido_sucessao (
    sigla           varchar primary key,
    sucessor        varchar not null,
    data_decisao    date not null
);

create table deputado (
    id_camara       varchar primary key,
    nome            varchar not null,
    nome_civil      varchar,
    cpf             varchar,
    sexo            varchar,
    nascimento      date
);

create table votacao (
    id              varchar primary key,
    casa            varchar not null,            -- 'camara' | 'senado' | ...
    data            date not null,
    data_hora       timestamp,
    orgao           varchar not null,
    descricao       varchar not null,
    nominal         boolean not null,
    sem_votos_individuais boolean not null,      -- secreta, ou registro duplicado sob outro id
    tipo            varchar not null,            -- merito | procedimento | eleicao | indefinido
    legislatura     integer
);

create table voto (
    id_votacao        varchar not null,
    id_camara         varchar not null,
    data_hora         timestamp,
    voto_original     varchar,
    voto_codificado   tinyint,                   -- 1 Sim | 0 Não/Obstrução | null
    partido_original  varchar,
    partido           varchar,                   -- harmonizado; null = sem partido
    uf                varchar,
    primary key (id_votacao, id_camara)
);

create table orientacao (
    id_votacao              varchar not null,
    bancada                 varchar not null,
    orientacao_original     varchar,
    orientacao_codificada   tinyint,             -- 1 Sim | 0 Não/Obstrução | null (liberado, vazio)
    primary key (id_votacao, bancada)
);

-- Votações usadas em todas as medidas (metodologia, seção 3): nominais de plenário com votos
-- individuais, exceto eleições de pessoas.
create view votacao_valida as
select * from votacao
where orgao = 'PLEN' and nominal and not sem_votos_individuais and tipo <> 'eleicao';

-- Filiação derivada do partido registrado em cada voto: períodos contínuos.
create table filiacao (
    id_camara   varchar not null,
    partido     varchar,
    inicio      date not null,
    fim         date not null
);
