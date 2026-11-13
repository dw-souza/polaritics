import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReguaCamara } from "@/components/ReguaCamara";
import { VOTACOES, formatarData, formatarNota, formatarPct, lerVisao, type Votacoes } from "@/lib/escala";
import {
  URL_METODOLOGIA_MUNICIPAL,
  hrefCamara,
  legislaturas,
  municipio,
  vereadoresDaLegislatura,
  type LegislaturaMunicipal,
  type LinhaVereador,
} from "@/lib/municipal";

import estilos from "../camaras.module.css";

export async function generateMetadata({
  params,
}: PageProps<"/camaras/[municipio]">): Promise<Metadata> {
  const m = await municipio((await params).municipio);
  return { title: m ? `Câmara de ${m.nome}` : "Câmara municipal" };
}

export default function PaginaCamara(props: PageProps<"/camaras/[municipio]">) {
  return (
    <Suspense fallback={<p className="discreto">Carregando a câmara…</p>}>
      <Camara {...props} />
    </Suspense>
  );
}

const ano = (d: string) => d.slice(0, 4);
const DIAS_SEM_DADOS = 60;

async function Camara({ params, searchParams }: PageProps<"/camaras/[municipio]">) {
  const { municipio: slug } = await params;
  const busca = await searchParams;
  const { votacoes } = lerVisao(busca);
  const m = await municipio(slug);
  if (!m) notFound();
  const legs = await legislaturas(slug);
  if (legs.length === 0) notFound();
  const pedida = Number(busca.legislatura);
  const leg = legs.find((l) => l.numero === pedida) ?? legs[0];
  const publicada = leg.variantes.includes(votacoes);
  const linhas = await vereadoresDaLegislatura(slug, leg.numero, votacoes);
  const comPosicao = linhas.flatMap((l) => (l.posicao ? [l.posicao] : []));
  const hrefVereador = (id: string) => `/camaras/${slug}/vereador/${id}`;
  const unanimes = leg.n_votacoes > 0 ? 1 - leg.n_divergentes / leg.n_votacoes : null;
  const grupos = new Set(comPosicao.map((p) => p.grupo)).size;

  return (
    <>
      <section className="cabeca-pagina">
        <p className="rotulo">
          <Link href="/camaras">Câmaras municipais</Link>
        </p>
        <h1>
          Câmara de {m.nome}
          <span className={estilos.uf}>{m.uf}</span>
        </h1>
        <p>
          Como votam os vereadores de {m.nome}, onde ficam na escala política e quanto acompanham
          o prefeito. Só com os dados oficiais da própria câmara.
        </p>
      </section>

      <section className="secao">
        <div className="secao-cab">
          <nav className="seg" aria-label="Legislatura">
            {legs.map((l) => (
              <Link
                key={l.numero}
                href={hrefCamara(slug, l.numero === legs[0].numero ? null : l.numero, votacoes)}
                aria-current={l.numero === leg.numero ? "true" : undefined}
                scroll={false}
              >
                {l.numero}ª · {ano(l.inicio)}–{ano(l.fim)}
              </Link>
            ))}
          </nav>
          <nav className="seg" aria-label="Votações consideradas">
            {(Object.keys(VOTACOES) as Votacoes[]).map((v) => (
              <Link
                key={v}
                href={hrefCamara(slug, leg.numero === legs[0].numero ? null : leg.numero, v)}
                aria-current={v === votacoes ? "true" : undefined}
                scroll={false}
              >
                {VOTACOES[v].nome}
              </Link>
            ))}
          </nav>
        </div>
        <Fatos leg={leg} unanimes={unanimes} grupos={grupos} n={comPosicao.length} />
        {leg.dados_ate && leg.em_curso && (leg.dias_sem_dados ?? 0) > DIAS_SEM_DADOS && (
          <p className="aviso" style={{ marginTop: 16 }}>
            <strong>Dados parados.</strong> A câmara não registra votações no seu sistema (SAPL)
            desde {formatarData(leg.dados_ate)}. Os números refletem só o que foi publicado até
            essa data.
          </p>
        )}
      </section>

      <section className="secao">
        <div className="secao-cab">
          <h2>Onde cada vereador está na régua</h2>
          <span className="rotulo">Pontos: posição · traço: 90% de certeza</span>
        </div>
        {publicada && comPosicao.length > 0 ? (
          <>
            <ReguaCamara posicoes={comPosicao} hrefVereador={hrefVereador} />
            <p className="pequeno discreto leitura" style={{ marginTop: 16 }}>
              Cada bloco reúne vereadores que votam de forma indistinguível com as votações
              disponíveis: a ordem entre eles pode mudar com poucos votos. A régua é calibrada pelos
              vereadores de partidos que especialistas classificam como de esquerda e de direita.{" "}
              <a href={URL_METODOLOGIA_MUNICIPAL}>Como é calculado</a>
            </p>
          </>
        ) : (
          <p className="aviso">
            <strong>Posição não publicada.</strong> Esta legislatura e variante não passaram nos
            critérios de validação (por exemplo, por ter poucas votações com divergência). O
            governismo e a presença abaixo não dependem do modelo.
          </p>
        )}
      </section>

      <section className="secao">
        <div className="secao-cab">
          <h2>Todos os vereadores</h2>
        </div>
        <Tabela linhas={linhas} hrefVereador={hrefVereador} publicada={publicada} />
      </section>
    </>
  );
}

function Fatos({
  leg,
  unanimes,
  grupos,
  n,
}: {
  leg: LegislaturaMunicipal;
  unanimes: number | null;
  grupos: number;
  n: number;
}) {
  return (
    <div className={estilos.fatos}>
      <div>
        <span className="rotulo">Votações nominais</span>
        <span className={`${estilos.grande} num`}>{leg.n_votacoes.toLocaleString("pt-BR")}</span>
        <span className="pequeno discreto">
          {leg.dados_ate ? `até ${formatarData(leg.dados_ate)}` : "na legislatura"}
        </span>
      </div>
      {unanimes !== null && (
        <div>
          <span className="rotulo">Sem nenhum voto contrário</span>
          <span className={`${estilos.grande} num`}>
            <span className="marca">{formatarPct(unanimes)}</span>
          </span>
          <span className="pequeno discreto">
            Só {leg.n_divergentes} votações tiveram divergência, e só elas dizem algo sobre a
            posição.
          </span>
        </div>
      )}
      {n > 0 && (
        <div>
          <span className="rotulo">Grupos que se distinguem</span>
          <span className={`${estilos.grande} num`}>{grupos}</span>
          <span className="pequeno discreto">entre {n} vereadores com posição estimada</span>
        </div>
      )}
      {leg.prefeito && (
        <div>
          <span className="rotulo">Prefeito no período</span>
          <span className={estilos.medio}>{leg.prefeito}</span>
          <span className="pequeno discreto">{leg.partido_prefeito}</span>
        </div>
      )}
    </div>
  );
}

function Tabela({
  linhas,
  hrefVereador,
  publicada,
}: {
  linhas: LinhaVereador[];
  hrefVereador: (id: string) => string;
  publicada: boolean;
}) {
  const ordenadas = [...linhas].sort(
    (a, b) => (a.posicao?.posicao ?? 99) - (b.posicao?.posicao ?? 99) || a.nome.localeCompare(b.nome),
  );
  return (
    <div className="tabela-rolagem">
      <table>
        <thead>
          <tr>
            <th>Vereador</th>
            <th>Partido</th>
            <th>Posição pelos votos</th>
            <th className="n">Na câmara</th>
            <th className="n">Com o prefeito</th>
            <th className="n">Presença</th>
          </tr>
        </thead>
        <tbody>
          {ordenadas.map((l) => (
            <tr key={l.id_vereador}>
              <td>
                <Link href={hrefVereador(l.id_vereador)}>{l.nome}</Link>
              </td>
              <td>{l.partido ?? "—"}</td>
              <td>
                {l.posicao ? (
                  <>
                    <span className="num">{formatarNota(l.posicao.nota)}</span>{" "}
                    <span className="discreto">{l.posicao.faixa_exibida.toLowerCase()}</span>
                  </>
                ) : (
                  <span className="discreto">
                    {publicada ? "votos insuficientes" : "não publicada"}
                  </span>
                )}
              </td>
              <td className="n">
                {l.posicao ? `${l.posicao.posicao}º de ${l.posicao.n_vereadores}` : "—"}
              </td>
              <td className="n">
                {l.gov_suficiente && l.gov_taxa !== null
                  ? formatarPct(l.gov_taxa)
                  : l.gov_n
                    ? `${l.gov_alinhados ?? 0} de ${l.gov_n}`
                    : "—"}
              </td>
              <td className="n">{l.presenca !== null ? formatarPct(l.presenca) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="pequeno discreto" style={{ marginTop: 12 }}>
        <strong>Na câmara:</strong> ordem da esquerda para a direita (1º = mais à esquerda).{" "}
        <strong>Com o prefeito:</strong> votos a favor dos projetos do prefeito nas votações em que
        alguém votou contra; com menos de 5 dessas votações, mostramos a contagem.{" "}
        <strong>Presença:</strong> sessões ordinárias e extraordinárias com lista registrada.
      </p>
    </div>
  );
}
