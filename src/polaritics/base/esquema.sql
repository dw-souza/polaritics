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
    data_decisao    date not null,
    tipo            varchar not null             -- incorporacao | fusao
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

create table votacao_proposicao (
    id_votacao      varchar not null,
    id_proposicao   varchar not null,
    sigla_tipo      varchar,
    numero          varchar,
    ano             varchar,
    ementa          varchar
);

-- Proposição principal de cada votação: prioriza o projeto (PEC, PL, MP...) sobre
-- requerimentos e outros documentos ligados à mesma votação.
create view votacao_proposicao_principal as
select * from votacao_proposicao
qualify row_number() over (
    partition by id_votacao
    order by case sigla_tipo when 'PEC' then 1 when 'PLP' then 2 when 'PL' then 3
                             when 'MPV' then 4 when 'PLV' then 5 when 'PDL' then 6
                             when 'PRC' then 7 else 9 end,
             id_proposicao
) = 1;

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

-- Âncora da escala 0–10: notas de especialistas por partido (coleta/especialistas.py).
create table nota_especialistas (
    partido         varchar primary key,
    nota            double not null,
    n_respostas     integer,
    desvio_padrao   double,
    onda            integer not null,
    origem          varchar not null             -- direta | fusão de X + Y
);

-- Períodos em exercício do mandato (posse/reassunção até licença/fim), da API de histórico.
create table exercicio (
    id_camara   varchar not null,
    legislatura integer not null,
    inicio      date not null,
    fim         date not null
);

-- Cota parlamentar (CEAP): uma linha por documento reembolsado.
create table despesa (
    id_camara   varchar not null,
    uf          varchar,
    ano         integer not null,
    mes         integer not null,
    categoria   varchar,
    fornecedor  varchar,
    cnpj_cpf    varchar,
    valor       double not null
);

-- Valor mensal da cota por UF (Ato da Mesa 270/2023), usado como peso entre estados.
create table cota_uf (
    uf      varchar primary key,
    valor   double not null
);

-- Sessões deliberativas do plenário e presenças registradas nelas.
create table sessao (
    id      varchar primary key,
    data    date not null
);

create table presenca (
    id_sessao   varchar not null,
    id_camara   varchar not null
);

-- Proposições (PL, PLP, PEC, PDL) e seus autores.
create table proposicao (
    id              varchar primary key,
    sigla_tipo      varchar not null,
    numero          varchar,
    ano             integer,
    ementa          varchar,
    situacao        varchar
);

create table autoria (
    id_proposicao   varchar not null,
    id_camara       varchar not null,
    ordem           integer,
    proponente      boolean
);
