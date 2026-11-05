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
  partido: string | null;
  uf: string | null;
  faixa_exibida: string | null;
  nota: number | null;
};

export type Deputado = {
  id_camara: string;
  nome: string;
  nome_civil: string | null;
  foto_url: string;
  partido: string | null;
  uf: string | null;
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
    select d.id_camara, d.nome, m.partido_atual as partido, m.uf, p.faixa_exibida, p.nota
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
    select d.id_camara, d.nome, d.nome_civil, d.foto_url, m.partido_atual as partido, m.uf
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
