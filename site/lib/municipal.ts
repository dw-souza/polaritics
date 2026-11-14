// Leitura do schema `municipal` no Neon (docs/metodologia-municipal.md). Mesma política de
// cache do schema `publicado`: os dados mudam uma vez por semana.
import { cacheLife, cacheTag } from "next/cache";

import { sql } from "./db";
import type { Votacoes } from "./escala";

export type Municipio = { municipio: string; nome: string; uf: string; sapl: string };

export type LegislaturaMunicipal = {
  numero: number;
  inicio: string;
  fim: string;
  prefeito: string | null;
  partido_prefeito: string | null;
  n_votacoes: number;
  n_divergentes: number;
  variantes: string[]; // variantes da posição aprovadas na validação
  versao_metodologia: string | null;
  dados_ate: string | null;
  dias_sem_dados: number | null;
  em_curso: boolean;
};

export type PosicaoVereador = {
  legislatura: number;
  variante: Votacoes;
  id_vereador: string;
  nome: string;
  foto_url: string | null;
  partido: string | null;
  nota: number;
  nota_p05: number;
  nota_p95: number;
  faixa: string;
  faixa_exibida: string;
  fronteira: boolean;
  posicao: number;
  posicao_p05: number;
  posicao_p95: number;
  n_vereadores: number;
  grupo: number;
  tamanho_grupo: number;
  grupo_polo: "esquerda" | "direita" | null;
  polo_unico: boolean;
  n_votos: number;
};

export type LinhaVereador = {
  id_vereador: string;
  nome: string;
  foto_url: string | null;
  partido: string | null;
  n_votos: number;
  posicao: PosicaoVereador | null;
  gov_taxa: number | null;
  gov_alinhados: number | null;
  gov_n: number | null;
  gov_suficiente: boolean;
  presenca: number | null;
  aprovados: number | null;
  viagens: number | null;
  custo_atribuido: number | null;
};

export type Vereador = {
  id_vereador: string;
  nome: string;
  nome_completo: string | null;
  sexo: string | null;
  foto_url: string | null;
};

export type MandatoVereador = {
  legislatura: number;
  partido: string | null;
  n_votos: number;
  prefeito: string | null;
  partido_prefeito: string | null;
  inicio: string;
  fim: string;
  n_divergentes: number;
  variantes: string[];
  gov_n_total: number | null;
  gov_n_disputadas: number | null;
  gov_alinhados: number | null;
  gov_taxa: number | null;
  gov_suficiente: boolean | null;
  pres_sessoes: number | null;
  pres_presentes: number | null;
  pres_taxa: number | null;
  pres_suficiente: boolean | null;
};

export type VotacaoMunicipal = {
  ordem: number;
  id_votacao: string;
  data: string;
  materia: string | null;
  ementa: string | null;
  tipo: string;
  voto: string;
  placar: string;
  url: string | null;
};

export async function municipios(): Promise<Municipio[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  return (await sql`
    select municipio, nome, uf, sapl from municipal.municipio order by nome`) as Municipio[];
}

export async function municipio(slug: string): Promise<Municipio | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [m] = await sql`
    select municipio, nome, uf, sapl from municipal.municipio where municipio = ${slug}`;
  return (m as Municipio) ?? null;
}

export async function legislaturas(slug: string): Promise<LegislaturaMunicipal[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  return (await sql`
    select l.numero, l.inicio::text as inicio, l.fim::text as fim, l.prefeito,
           l.partido_prefeito, l.n_votacoes, l.n_divergentes,
           coalesce(p.variantes, '{}') as variantes, p.versao_metodologia,
           p.dados_ate::text as dados_ate,
           (current_date - p.dados_ate)::int as dias_sem_dados,
           l.fim >= current_date as em_curso
    from municipal.legislatura l
    left join lateral (
        select variantes, versao_metodologia, dados_ate from municipal.publicacao p
        where p.municipio = l.municipio and p.legislatura = l.numero
        order by id desc limit 1) p on true
    where l.municipio = ${slug} and l.n_votacoes > 0
    order by l.numero desc`) as LegislaturaMunicipal[];
}

// Todos que votaram na legislatura, com posição (se publicada), governismo e presença.
export async function vereadoresDaLegislatura(
  slug: string,
  legislatura: number,
  variante: Votacoes,
): Promise<LinhaVereador[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [linhas, posicoes] = await Promise.all([
    sql`
      select m.id_vereador, v.nome, v.foto_url, m.partido, m.n_votos,
             g.taxa_disputadas as gov_taxa, g.alinhados_disputadas as gov_alinhados,
             g.n_disputadas as gov_n, coalesce(g.suficiente, false) as gov_suficiente,
             case when pr.suficiente then pr.taxa end as presenca,
             at.aprovados, vg.viagens, vg.custo_atribuido
      from municipal.mandato m
      join municipal.vereador v using (municipio, id_vereador)
      left join municipal.governismo g on g.municipio = m.municipio
           and g.legislatura = m.legislatura and g.id_vereador = m.id_vereador
      left join municipal.presenca pr on pr.municipio = m.municipio
           and pr.legislatura = m.legislatura and pr.id_vereador = m.id_vereador
      left join municipal.atividade at on at.municipio = m.municipio
           and at.legislatura = m.legislatura and at.id_vereador = m.id_vereador
      left join municipal.viagens vg on vg.municipio = m.municipio
           and vg.legislatura = m.legislatura and vg.id_vereador = m.id_vereador
      where m.municipio = ${slug} and m.legislatura = ${legislatura}
      order by v.nome`,
    sql`
      select
    p.legislatura, p.variante, p.id_vereador, v.nome, v.foto_url, p.partido, p.nota,
    p.nota_p05, p.nota_p95, p.faixa, p.faixa_exibida, p.fronteira, p.posicao, p.posicao_p05,
    p.posicao_p95, p.n_vereadores, p.grupo, p.tamanho_grupo, p.grupo_polo, p.polo_unico,
    p.n_votos
      from municipal.posicao p join municipal.vereador v using (municipio, id_vereador)
      where p.municipio = ${slug} and p.legislatura = ${legislatura}
        and p.variante = ${variante}`,
  ]);
  const porId = new Map((posicoes as PosicaoVereador[]).map((p) => [p.id_vereador, p]));
  return (linhas as Omit<LinhaVereador, "posicao">[]).map((l) => ({
    ...l,
    posicao: porId.get(l.id_vereador) ?? null,
  }));
}

export async function vereador(slug: string, id: string): Promise<Vereador | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [v] = await sql`
    select id_vereador, nome, nome_completo, sexo, foto_url from municipal.vereador
    where municipio = ${slug} and id_vereador = ${id}`;
  return (v as Vereador) ?? null;
}

export async function mandatosDoVereador(slug: string, id: string): Promise<MandatoVereador[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  return (await sql`
    select m.legislatura, m.partido, m.n_votos, l.prefeito, l.partido_prefeito,
           l.inicio::text as inicio, l.fim::text as fim, l.n_divergentes,
           coalesce((select variantes from municipal.publicacao p
                     where p.municipio = m.municipio and p.legislatura = m.legislatura
                     order by id desc limit 1), '{}') as variantes,
           g.n_total as gov_n_total, g.n_disputadas as gov_n_disputadas,
           g.alinhados_disputadas as gov_alinhados, g.taxa_disputadas as gov_taxa,
           g.suficiente as gov_suficiente,
           pr.sessoes as pres_sessoes, pr.presentes as pres_presentes, pr.taxa as pres_taxa,
           pr.suficiente as pres_suficiente
    from municipal.mandato m
    join municipal.legislatura l on l.municipio = m.municipio and l.numero = m.legislatura
    left join municipal.governismo g on g.municipio = m.municipio
         and g.legislatura = m.legislatura and g.id_vereador = m.id_vereador
    left join municipal.presenca pr on pr.municipio = m.municipio
         and pr.legislatura = m.legislatura and pr.id_vereador = m.id_vereador
    where m.municipio = ${slug} and m.id_vereador = ${id}
    order by m.legislatura desc`) as MandatoVereador[];
}

export async function posicoesDoVereador(slug: string, id: string): Promise<PosicaoVereador[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  return (await sql`
    select
    p.legislatura, p.variante, p.id_vereador, v.nome, v.foto_url, p.partido, p.nota,
    p.nota_p05, p.nota_p95, p.faixa, p.faixa_exibida, p.fronteira, p.posicao, p.posicao_p05,
    p.posicao_p95, p.n_vereadores, p.grupo, p.tamanho_grupo, p.grupo_polo, p.polo_unico,
    p.n_votos
    from municipal.posicao p join municipal.vereador v using (municipio, id_vereador)
    where p.municipio = ${slug} and p.id_vereador = ${id}`) as PosicaoVereador[];
}

export async function filiacoes(
  slug: string,
  id: string,
): Promise<{ partido: string; inicio: string; fim: string | null }[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  return (await sql`
    select partido, inicio::text as inicio, fim::text as fim from municipal.filiacao
    where municipio = ${slug} and id_vereador = ${id}
    order by inicio`) as { partido: string; inicio: string; fim: string | null }[];
}

export async function votacoesQueMaisPesaram(
  slug: string,
  id: string,
  legislatura: number,
  variante: Votacoes,
): Promise<VotacaoMunicipal[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  return (await sql`
    select ordem, id_votacao, data::text as data, materia, ementa, tipo, voto, placar, url
    from municipal.votacao_explicativa
    where municipio = ${slug} and id_vereador = ${id} and legislatura = ${legislatura}
      and variante = ${variante}
    order by ordem`) as VotacaoMunicipal[];
}

export async function notasDosPartidos(): Promise<Record<string, number>> {
  "use cache";
  cacheLife("hours");
  cacheTag("publicacao");
  const linhas = await sql`
    select sigla, nota_especialistas from publicado.partido where nota_especialistas is not null`;
  return Object.fromEntries(linhas.map((l) => [l.sigla as string, l.nota_especialistas as number]));
}

export const cargoVereador = (sexo: string | null) =>
  sexo === "F" ? "Vereadora" : sexo === "M" ? "Vereador" : "Vereador(a)";

export const ordinal = (n: number) => `${n}º`;

export const URL_METODOLOGIA_MUNICIPAL =
  "https://github.com/dw-souza/polaritics/blob/main/docs/metodologia-municipal.md";

export function hrefCamara(slug: string, legislatura: number | null, votacoes: Votacoes) {
  const q = new URLSearchParams();
  if (legislatura !== null) q.set("legislatura", String(legislatura));
  if (votacoes !== "todas") q.set("votacoes", votacoes);
  const s = q.toString();
  return s ? `/camaras/${slug}?${s}` : `/camaras/${slug}`;
}

// Ficha do vereador; sem legislatura, abre na mais recente em que ele votou.
export function hrefVereador(
  slug: string,
  id: string,
  legislatura: number | null,
  votacoes: Votacoes,
) {
  const q = new URLSearchParams();
  if (legislatura !== null) q.set("legislatura", String(legislatura));
  if (votacoes !== "todas") q.set("votacoes", votacoes);
  const s = q.toString();
  return s ? `/camaras/${slug}/vereador/${id}?${s}` : `/camaras/${slug}/vereador/${id}`;
}

export type Atividade = {
  apresentados: number;
  aprovados: number;
  aprovados_denominacao: number;
  projetos: { titulo: string; ementa: string | null; data: string | null; url: string | null }[];
};

export type Viagem = {
  numero: number;
  ano: number;
  data: string | null;
  ementa: string | null;
  custo: number;
  n_vereadores: number;
  url: string | null;
};

export type Viagens = {
  viagens: number;
  custo_atribuido: number;
  custo_das_viagens: number;
  lista: Viagem[];
};

export type Campanha = {
  ano_eleicao: number;
  partido: string | null;
  situacao: string | null;
  receita: number;
  fundo_especial: number;
  fundo_partidario: number;
  proprios: number;
  pessoas_fisicas: number;
  outros: number;
  despesa: number;
};

export type Estrutura = {
  ano: number;
  mes: number;
  vereadores: number;
  subsidio: number | null;
  assessores: number;
  custo_assessores: number | null;
  viagens_por_ano: { ano: number; total: number; com_vereador: number; sem_piv: number }[];
};

// Projetos como primeiro autor (M9); a lista traz os aprovados que não são só denominações.
export async function atividade(slug: string, id: string, legislatura: number): Promise<Atividade | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [[linha], projetos] = await Promise.all([
    sql`select apresentados, aprovados, aprovados_denominacao from municipal.atividade
        where municipio = ${slug} and id_vereador = ${id} and legislatura = ${legislatura}`,
    sql`select titulo, ementa, data::text as data, url from municipal.projeto_aprovado
        where municipio = ${slug} and id_vereador = ${id} and legislatura = ${legislatura}
          and not denominacao
        order by data desc`,
  ]);
  if (!linha) return null;
  return { ...(linha as Omit<Atividade, "projetos">), projetos: projetos as Atividade["projetos"] };
}

export async function viagens(slug: string, id: string, legislatura: number): Promise<Viagens | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [[linha], lista] = await Promise.all([
    sql`select viagens, custo_atribuido, custo_das_viagens from municipal.viagens
        where municipio = ${slug} and id_vereador = ${id} and legislatura = ${legislatura}`,
    sql`select v.numero, v.ano, v.data::text as data, v.ementa, v.custo, v.n_vereadores, v.url
        from municipal.viagem v
        join municipal.viagem_vereador vv using (municipio, numero, ano)
        where v.municipio = ${slug} and vv.id_vereador = ${id} and v.legislatura = ${legislatura}
        order by v.custo desc`,
  ]);
  if (!linha) return null;
  return { ...(linha as Omit<Viagens, "lista">), lista: lista as Viagem[] };
}

export async function campanha(slug: string, id: string, legislatura: number): Promise<Campanha | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [linha] = await sql`
    select ano_eleicao, partido, situacao, receita, fundo_especial, fundo_partidario, proprios,
           pessoas_fisicas, outros, despesa
    from municipal.campanha
    where municipio = ${slug} and id_vereador = ${id} and legislatura = ${legislatura}`;
  return (linha as Campanha) ?? null;
}

// Retrato da câmara (M11): o mês mais recente da folha e o gasto com viagens por ano.
export async function estrutura(slug: string): Promise<Estrutura | null> {
  "use cache";
  cacheLife("hours");
  cacheTag("municipal");
  const [[folha], porAno] = await Promise.all([
    sql`select ano, mes, vereadores, subsidio, assessores, custo_assessores
        from municipal.folha_mes where municipio = ${slug} and vereadores > 0
        order by ano desc, mes desc limit 1`,
    sql`select ano, total, com_vereador, sem_piv from municipal.viagem_ano
        where municipio = ${slug} order by ano`,
  ]);
  if (!folha) return null;
  return {
    ...(folha as Omit<Estrutura, "viagens_por_ano">),
    viagens_por_ano: porAno as Estrutura["viagens_por_ano"],
  };
}

// Situação na eleição como o TSE registra, em texto corrido.
const SITUACOES: Record<string, string> = {
  "ELEITO POR QP": "eleito pelo quociente partidário",
  "ELEITO POR MÉDIA": "eleito pela média",
  SUPLENTE: "suplente",
  "NÃO ELEITO": "não eleito",
};
export const situacaoEleitoral = (s: string | null) => (s ? (SITUACOES[s] ?? s.toLowerCase()) : "");
