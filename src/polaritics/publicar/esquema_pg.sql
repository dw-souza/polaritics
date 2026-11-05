-- Esquema de publicação no Postgres (Neon). Lido pelo site; só contém resultados validados.
-- Cada carga substitui as linhas da legislatura publicada; o histórico fica em `publicacao`.

create schema if not exists publicado;

-- id e publicado_em são preenchidos pela carga (o DuckDB grava via COPY, sem usar defaults)
create table if not exists publicado.publicacao (
    id                  bigint primary key,
    legislatura         integer not null,
    versao_metodologia  text not null,
    variantes           text[] not null,
    dados_ate           date not null,
    publicado_em        timestamptz not null
);

create table if not exists publicado.partido (
    sigla               text primary key,
    nota_especialistas  double precision,
    origem_nota         text
);

create table if not exists publicado.deputado (
    id_camara   text primary key,
    nome        text not null,
    nome_civil  text,
    sexo        text,
    foto_url    text
);

create table if not exists publicado.mandato (
    id_camara       text not null,
    legislatura     integer not null,
    partido_atual   text,
    uf              text,
    primary key (id_camara, legislatura)
);

-- regua: 'voto' (visão principal, partidos-polo) | 'campo' (comparação com o próprio partido)
-- variante: 'todas' | 'merito'
create table if not exists publicado.posicao (
    id_camara           text not null,
    legislatura         integer not null,
    variante            text not null,
    regua               text not null,
    nota                double precision not null,
    nota_p05            double precision not null,
    nota_p95            double precision not null,
    faixa               text not null,
    faixa_exibida       text not null,     -- faixa, ou "Entre X e Y" na zona de fronteira
    fronteira           boolean not null,
    n_votos             integer not null,
    versao_metodologia  text not null,
    primary key (id_camara, legislatura, variante, regua)
);

create table if not exists publicado.posicao_partido (
    partido             text not null,
    legislatura         integer not null,
    variante            text not null,
    n_deputados         integer not null,
    nota_votos          double precision not null,
    faixa_votos         text not null,
    nota_especialistas  double precision,
    primary key (partido, legislatura, variante)
);

-- periodo: 'legislatura' ou o ano ('2023', '2024', ...)
create table if not exists publicado.governismo (
    id_camara               text not null,
    legislatura             integer not null,
    governo                 text not null,
    periodo                 text not null,
    n_total                 integer not null,
    taxa_total              double precision,
    n_disputadas            integer not null,
    taxa_disputadas         double precision,
    suficiente              boolean not null,
    primary key (id_camara, legislatura, governo, periodo)
);

create table if not exists publicado.fidelidade (
    id_camara   text not null,
    legislatura integer not null,
    periodo     text not null,
    n           integer not null,
    taxa        double precision,
    suficiente  boolean not null,
    primary key (id_camara, legislatura, periodo)
);

create table if not exists publicado.votacao_explicativa (
    id_camara           text not null,
    legislatura         integer not null,
    variante            text not null,
    ordem               integer not null,
    id_votacao          text not null,
    data                date not null,
    descricao           text not null,
    tipo                text not null,     -- merito | procedimento | indefinido
    proposicao          text,              -- ex.: "PL 1026/2024"
    ementa              text,
    url_proposicao      text,
    voto                text,
    orientacao_governo  text,
    peso                double precision not null,
    url                 text not null,     -- registro oficial da votação (Dados Abertos)
    primary key (id_camara, legislatura, variante, ordem)
);

create table if not exists publicado.validacao (
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

create index if not exists posicao_legislatura on publicado.posicao (legislatura, variante, regua);
create index if not exists governismo_legislatura on publicado.governismo (legislatura, periodo);

-- Gastos da cota (exceto passagens emitidas pela Câmara, ausentes dos dados abertos).
-- periodo: 'legislatura' ou o ano; relativo = gasto mensal ÷ cota do estado (Ato 270/2023).
create table if not exists publicado.gastos (
    id_camara   text not null,
    legislatura integer not null,
    periodo     text not null,
    uf          text,
    meses       double precision not null,
    total       double precision not null,
    por_mes     double precision,
    relativo    double precision,
    suficiente  boolean not null,
    primary key (id_camara, legislatura, periodo)
);

create table if not exists publicado.gastos_categoria (
    id_camara   text not null,
    legislatura integer not null,
    categoria   text not null,
    valor       double precision not null,
    primary key (id_camara, legislatura, categoria)
);

-- Até 5 maiores fornecedores; pessoa física aparece sem nome.
create table if not exists publicado.gastos_fornecedor (
    id_camara   text not null,
    legislatura integer not null,
    ordem       integer not null,
    fornecedor  text not null,
    cnpj        text,
    valor       double precision not null,
    primary key (id_camara, legislatura, ordem)
);

-- Presença nas sessões deliberativas do plenário em que o deputado estava em exercício.
create table if not exists publicado.presenca (
    id_camara   text not null,
    legislatura integer not null,
    periodo     text not null,
    sessoes     integer not null,
    presentes   integer not null,
    taxa        double precision not null,
    suficiente  boolean not null,
    primary key (id_camara, legislatura, periodo)
);

-- PL, PLP, PEC e PDL apresentados como primeiro autor na legislatura.
create table if not exists publicado.atividade (
    id_camara           text not null,
    legislatura         integer not null,
    apresentados        integer not null,
    aprovados_camara    integer not null,
    viraram_lei         integer not null,
    suficiente          boolean not null,
    primary key (id_camara, legislatura)
);

create table if not exists publicado.atividade_aprovadas (
    id_camara       text not null,
    legislatura     integer not null,
    id_proposicao   text not null,
    proposicao      text not null,
    ementa          text,
    situacao        text not null,
    url             text not null,
    primary key (id_camara, legislatura, id_proposicao)
);
