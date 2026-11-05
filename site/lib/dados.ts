// Leitura do schema `publicado` no Neon. Os dados mudam uma vez por semana (atualização de
// sábado), então cada consulta fica em cache por algumas horas.
import { cacheLife, cacheTag } from "next/cache";

import { sql } from "./db";
import type { Regua, Votacoes } from "./escala";

export type Publicacao = {
  legislatura: number;
  versao_metodologia: string;
  variantes: string[];
  dados_ate: string;
  publicado_em: string;
};

export type DeputadoResumo = {
  id_camara: string;
  nome: string;
  foto_url: string;
  partido: string | null;
  uf: string | null;
  faixa_exibida: string | null;
  fronteira: boolean | null;
  nota: number | null;
};

export type Deputado = {
  id_camara: string;
  nome: string;
  nome_civil: string | null;
  sexo: string | null;
  foto_url: string;
  partido: string | null;
  uf: string | null;
};

export type Fatos = {
  direita_especialistas: number | null;
  direita_votos: number | null;
  partidos_direita: string[];
  governismo_mediano: number | null;
  em_fronteira: number;
  com_posicao: number;
};

export type LinhaRanking = {
  id_camara: string;
  nome: string;
  foto_url: string;
  partido: string | null;
  uf: string | null;
  valor: number;
  n: number;
  extra: number | null;
};

export type Gastos = {
  periodo: string;
  uf: string | null;
  meses: number;
  total: number;
  por_mes: number | null;
  relativo: number | null;
  suficiente: boolean;
};

export type Presenca = {
  periodo: string;
  sessoes: number;
  presentes: number;
  taxa: number;
  suficiente: boolean;
};

export type Atividade = {
  apresentados: number;
  aprovados_camara: number;
  viraram_lei: number;
  suficiente: boolean;
  aprovadas: { proposicao: string; ementa: string | null; situacao: string; url: string }[];
};

export type Posicao = {
  variante: Votacoes;
  regua: Regua;
  nota: number;
  nota_p05: number;
  nota_p95: number;
  faixa: string;
  faixa_exibida: string;
  fronteira: boolean;
  n_votos: number;
};

export type PosicaoPartido = {
  partido: string;
  variante: Votacoes;
  n_deputados: number;
  nota_votos: number;
  faixa_votos: string;
  nota_especialistas: number | null;
};

export type Governismo = {
  governo: string;
  periodo: string;
  n_total: number;
  taxa_total: number | null;
  n_disputadas: number;
  taxa_disputadas: number | null;
  suficiente: boolean;
};

export type Fidelidade = { periodo: string; n: number; taxa: number | null; suficiente: boolean };

export type VotacaoExplicativa = {
  ordem: number;
  id_votacao: string;
  data: string;
  descricao: string;
  tipo: string;
  proposicao: string | null;
  ementa: string | null;
  url_proposicao: string | null;
  voto: string | null;
  orientacao_governo: string | null;
  url: string;
};

export type PartidoLinha = PosicaoPartido & {
  governismo_disputadas: number | null;
};

export async function publicacaoAtual(): Promise<Publicacao | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const linhas = await sql`
    select legislatura, versao_metodologia, variantes, dados_ate::text as dados_ate,
           publicado_em::text as publicado_em
    from publicado.publicacao order by id desc limit 1`;
  return (linhas[0] as Publicacao) ?? null;
}

export async function listaDeputados(legislatura: number): Promise<DeputadoResumo[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select d.id_camara, d.nome, d.foto_url, m.partido_atual as partido, m.uf, p.faixa_exibida,
           p.fronteira, p.nota
    from publicado.mandato m
    join publicado.deputado d using (id_camara)
    left join publicado.posicao p on p.id_camara = m.id_camara and p.legislatura = m.legislatura
         and p.regua = 'voto' and p.variante = 'todas'
    where m.legislatura = ${legislatura}
    order by d.nome`) as DeputadoResumo[];
}

export async function deputado(id: string, legislatura: number): Promise<Deputado | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const linhas = await sql`
    select d.id_camara, d.nome, d.nome_civil, d.sexo, d.foto_url, m.partido_atual as partido, m.uf
    from publicado.deputado d
    join publicado.mandato m on m.id_camara = d.id_camara and m.legislatura = ${legislatura}
    where d.id_camara = ${id}`;
  return (linhas[0] as Deputado) ?? null;
}

export async function posicoes(id: string, legislatura: number): Promise<Posicao[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select variante, regua, nota, nota_p05, nota_p95, faixa, faixa_exibida, fronteira, n_votos
    from publicado.posicao where id_camara = ${id} and legislatura = ${legislatura}`) as Posicao[];
}

export async function posicaoPartido(
  partido: string,
  legislatura: number,
): Promise<{ especialistas: number | null; origem: string | null; votos: PosicaoPartido[] }> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const [nota] = await sql`
    select nota_especialistas, origem_nota from publicado.partido where sigla = ${partido}`;
  const votos = (await sql`
    select partido, variante, n_deputados, nota_votos, faixa_votos, nota_especialistas
    from publicado.posicao_partido
    where partido = ${partido} and legislatura = ${legislatura}`) as PosicaoPartido[];
  return {
    especialistas: (nota?.nota_especialistas as number | undefined) ?? null,
    origem: (nota?.origem_nota as string | undefined) ?? null,
    votos,
  };
}

export async function governismo(id: string, legislatura: number): Promise<Governismo[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select governo, periodo, n_total, taxa_total, n_disputadas, taxa_disputadas, suficiente
    from publicado.governismo where id_camara = ${id} and legislatura = ${legislatura}
    order by periodo`) as Governismo[];
}

export async function fidelidade(id: string, legislatura: number): Promise<Fidelidade[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select periodo, n, taxa, suficiente from publicado.fidelidade
    where id_camara = ${id} and legislatura = ${legislatura} order by periodo`) as Fidelidade[];
}

export async function votacoesExplicativas(
  id: string,
  legislatura: number,
  variante: Votacoes,
): Promise<VotacaoExplicativa[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select ordem, id_votacao, data::text as data, descricao, tipo, proposicao, ementa,
           url_proposicao, voto, orientacao_governo, url
    from publicado.votacao_explicativa
    where id_camara = ${id} and legislatura = ${legislatura} and variante = ${variante}
    order by ordem`) as VotacaoExplicativa[];
}

export async function partidos(legislatura: number, variante: Votacoes): Promise<PartidoLinha[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select pp.partido, pp.variante, pp.n_deputados, pp.nota_votos, pp.faixa_votos,
           pp.nota_especialistas,
           (select percentile_cont(0.5) within group (order by g.taxa_disputadas)
              from publicado.governismo g
              join publicado.mandato m on m.id_camara = g.id_camara
                   and m.legislatura = g.legislatura
             where g.legislatura = pp.legislatura and g.periodo = 'legislatura'
               and g.suficiente and m.partido_atual = pp.partido) as governismo_disputadas
    from publicado.posicao_partido pp
    where pp.legislatura = ${legislatura} and pp.variante = ${variante}
    order by pp.nota_votos`) as PartidoLinha[];
}

// Fatos da página inicial, calculados dos dados publicados (nada escrito à mão).
export async function fatos(legislatura: number): Promise<Fatos> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const [direita] = await sql`
    select percentile_cont(0.5) within group (order by nota_especialistas) as especialistas,
           percentile_cont(0.5) within group (order by nota_votos) as votos,
           array_agg(partido order by n_deputados desc) as partidos
    from publicado.posicao_partido
    where legislatura = ${legislatura} and variante = 'todas'
      and nota_especialistas > 7.0 and nota_especialistas <= 8.5`;
  const [gov] = await sql`
    select percentile_cont(0.5) within group (order by taxa_disputadas) as mediana
    from publicado.governismo
    where legislatura = ${legislatura} and periodo = 'legislatura' and suficiente`;
  const [fr] = await sql`
    select count(*) filter (where fronteira)::int as em_fronteira, count(*)::int as total
    from publicado.posicao
    where legislatura = ${legislatura} and variante = 'todas' and regua = 'voto'`;
  return {
    direita_especialistas: (direita?.especialistas as number | null) ?? null,
    direita_votos: (direita?.votos as number | null) ?? null,
    partidos_direita: (direita?.partidos as string[] | null) ?? [],
    governismo_mediano: (gov?.mediana as number | null) ?? null,
    em_fronteira: (fr?.em_fronteira as number) ?? 0,
    com_posicao: (fr?.total as number) ?? 0,
  };
}

// Rankings: só deputados com dados suficientes; a ordem e os filtros ficam na página.
export async function rankingGovernismo(legislatura: number): Promise<LinhaRanking[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select d.id_camara, d.nome, d.foto_url, m.partido_atual as partido, m.uf,
           g.taxa_disputadas as valor, g.n_disputadas as n, null as extra
    from publicado.governismo g
    join publicado.deputado d using (id_camara)
    join publicado.mandato m on m.id_camara = g.id_camara and m.legislatura = g.legislatura
    where g.legislatura = ${legislatura} and g.periodo = 'legislatura' and g.suficiente
    order by g.taxa_disputadas desc, d.nome`) as LinhaRanking[];
}

export async function rankingFidelidade(legislatura: number): Promise<LinhaRanking[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select d.id_camara, d.nome, d.foto_url, m.partido_atual as partido, m.uf,
           f.taxa as valor, f.n, null as extra
    from publicado.fidelidade f
    join publicado.deputado d using (id_camara)
    join publicado.mandato m on m.id_camara = f.id_camara and m.legislatura = f.legislatura
    where f.legislatura = ${legislatura} and f.periodo = 'legislatura' and f.suficiente
    order by f.taxa desc, d.nome`) as LinhaRanking[];
}

export async function gastos(
  id: string,
  legislatura: number,
): Promise<{
  periodos: Gastos[];
  categorias: { categoria: string; valor: number }[];
  fornecedores: { fornecedor: string; cnpj: string | null; valor: number }[];
}> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const [periodos, categorias, fornecedores] = await Promise.all([
    sql`select periodo, uf, meses, total, por_mes, relativo, suficiente from publicado.gastos
        where id_camara = ${id} and legislatura = ${legislatura} order by periodo`,
    sql`select categoria, valor from publicado.gastos_categoria
        where id_camara = ${id} and legislatura = ${legislatura} order by valor desc`,
    sql`select fornecedor, cnpj, valor from publicado.gastos_fornecedor
        where id_camara = ${id} and legislatura = ${legislatura} order by ordem`,
  ]);
  return {
    periodos: periodos as Gastos[],
    categorias: categorias as { categoria: string; valor: number }[],
    fornecedores: fornecedores as { fornecedor: string; cnpj: string | null; valor: number }[],
  };
}

export async function presenca(id: string, legislatura: number): Promise<Presenca[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select periodo, sessoes, presentes, taxa, suficiente from publicado.presenca
    where id_camara = ${id} and legislatura = ${legislatura} order by periodo`) as Presenca[];
}

export async function atividade(id: string, legislatura: number): Promise<Atividade | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const [linha] = await sql`
    select apresentados, aprovados_camara, viraram_lei, suficiente from publicado.atividade
    where id_camara = ${id} and legislatura = ${legislatura}`;
  if (!linha) return null;
  const aprovadas = await sql`
    select proposicao, ementa, situacao, url from publicado.atividade_aprovadas
    where id_camara = ${id} and legislatura = ${legislatura}
    order by situacao = 'Transformado em Norma Jurídica' desc, proposicao`;
  return { ...(linha as Omit<Atividade, "aprovadas">), aprovadas: aprovadas as Atividade["aprovadas"] };
}

// Gastos: valor = gasto mensal ÷ cota do estado (menor = mais econômico); extra = R$/mês.
export async function rankingGastos(legislatura: number): Promise<LinhaRanking[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select d.id_camara, d.nome, d.foto_url, m.partido_atual as partido, g.uf,
           g.relativo as valor, round(g.meses)::int as n, g.por_mes as extra
    from publicado.gastos g
    join publicado.deputado d using (id_camara)
    join publicado.mandato m on m.id_camara = g.id_camara and m.legislatura = g.legislatura
    where g.legislatura = ${legislatura} and g.periodo = 'legislatura' and g.suficiente
    order by g.relativo, d.nome`) as LinhaRanking[];
}

export async function rankingPresenca(legislatura: number): Promise<LinhaRanking[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select d.id_camara, d.nome, d.foto_url, m.partido_atual as partido, m.uf,
           p.taxa as valor, p.sessoes as n, p.presentes as extra
    from publicado.presenca p
    join publicado.deputado d using (id_camara)
    join publicado.mandato m on m.id_camara = p.id_camara and m.legislatura = p.legislatura
    where p.legislatura = ${legislatura} and p.periodo = 'legislatura' and p.suficiente
    order by p.taxa desc, d.nome`) as LinhaRanking[];
}

// Atividade: valor = projetos aprovados na Câmara; n = apresentados; extra = viraram lei.
export async function rankingAtividade(legislatura: number): Promise<LinhaRanking[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  return (await sql`
    select d.id_camara, d.nome, d.foto_url, m.partido_atual as partido, m.uf,
           a.aprovados_camara as valor, a.apresentados as n, a.viraram_lei as extra
    from publicado.atividade a
    join publicado.deputado d using (id_camara)
    join publicado.mandato m on m.id_camara = a.id_camara and m.legislatura = a.legislatura
    where a.legislatura = ${legislatura} and a.suficiente
    order by a.aprovados_camara desc, a.viraram_lei desc, d.nome`) as LinhaRanking[];
}
