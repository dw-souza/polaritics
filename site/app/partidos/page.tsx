import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { partidos, publicacaoAtual } from "@/lib/dados";
import {
  VOTACOES,
  faixa,
  formatarNota,
  formatarPct,
  hrefVisao,
  lerVisao,
  pos,
  type Votacoes,
} from "@/lib/escala";

import estilos from "./partidos.module.css";

export const metadata: Metadata = { title: "Partidos" };

export default function PaginaPartidos(props: PageProps<"/partidos">) {
  return (
    <>
      <section className="cabeca-pagina">
        <h1>O que os partidos dizem ser e como votam</h1>
        <p>
          A classificação feita por especialistas em ciência política, ao lado da posição da
          bancada pelos votos em plenário. Quanto maior a linha, maior a diferença.
        </p>
      </section>
      <Suspense fallback={<p className="discreto">Carregando…</p>}>
        <Conteudo {...props} />
      </Suspense>
    </>
  );
}

async function Conteudo({ searchParams }: PageProps<"/partidos">) {
  const { votacoes } = lerVisao(await searchParams);
  const pub = await publicacaoAtual();
  const linhas = pub ? await partidos(pub.legislatura, votacoes) : [];

  return (
    <>
      <section className="secao">
        <div className="secao-cab">
          <nav className="seg" aria-label="Votações consideradas">
            {(Object.keys(VOTACOES) as Votacoes[]).map((v) => (
              <Link
                key={v}
                href={hrefVisao("/partidos", "voto", v)}
                aria-current={v === votacoes ? "true" : undefined}
                scroll={false}
              >
                {VOTACOES[v].nome}
              </Link>
            ))}
          </nav>
          <ul className={estilos.legenda}>
            <li>
              <span className={`${estilos.chave} ${estilos.esp}`} aria-hidden="true" />
              Segundo especialistas
            </li>
            <li>
              <span className={`${estilos.chave} ${estilos.voto}`} aria-hidden="true" />
              Pelos votos (mediana da bancada)
            </li>
          </ul>
        </div>

        <div
          className={estilos.grafico}
          role="img"
          aria-label="Posição de cada partido segundo especialistas e pelos votos. Os valores estão na tabela abaixo."
        >
          {linhas.map((l) => {
            const esp = l.nota_especialistas;
            const [ini, fim] =
              esp === null ? [l.nota_votos, l.nota_votos] : [Math.min(esp, l.nota_votos), Math.max(esp, l.nota_votos)];
            return (
              <div key={l.partido} className={estilos.linha}>
                <span className={estilos.sigla}>{l.partido}</span>
                <div className={estilos.trilho}>
                  <div className={estilos.fundo} aria-hidden="true">
                    {[1, 2, 3, 4, 5, 6, 7].map((i) => (
                      <i key={i} style={{ color: `var(--faixa-${i})` }} />
                    ))}
                  </div>
                  {esp !== null && (
                    <span
                      className={estilos.ligacao}
                      style={{ left: pos(ini), width: `${(fim - ini) * 10}%` }}
                    />
                  )}
                  {esp !== null && (
                    <span
                      className={`${estilos.ponto} ${estilos.esp}`}
                      style={{ left: pos(esp) }}
                      title={`${l.partido} segundo especialistas: ${formatarNota(esp)}`}
                    />
                  )}
                  <span
                    className={`${estilos.ponto} ${estilos.voto}`}
                    style={{ left: pos(l.nota_votos) }}
                    title={`${l.partido} pelos votos: ${formatarNota(l.nota_votos)}`}
                  />
                </div>
              </div>
            );
          })}
          <div className={estilos.linha} aria-hidden="true">
            <span />
            <div className={estilos.eixo}>
              {[0, 2, 4, 6, 8, 10].map((v) => (
                <span key={v} style={{ left: pos(v) }}>
                  {v}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="secao">
        <div className="secao-cab">
          <h2>Os números</h2>
        </div>
        <div className="tabela-rolagem">
          <table>
            <thead>
              <tr>
                <th>Partido</th>
                <th className="n">Deputados</th>
                <th>Especialistas</th>
                <th>Pelos votos</th>
                <th className="n">Governismo</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.partido}>
                  <td>
                    <strong>{l.partido}</strong>
                  </td>
                  <td className="n">{l.n_deputados}</td>
                  <td>
                    {l.nota_especialistas !== null
                      ? `${faixa(l.nota_especialistas)} · ${formatarNota(l.nota_especialistas)}`
                      : "sem classificação"}
                  </td>
                  <td>
                    {l.faixa_votos} · {formatarNota(l.nota_votos)}
                  </td>
                  <td className="n">
                    {l.governismo_disputadas !== null ? formatarPct(l.governismo_disputadas) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className={estilos.nota}>
          Partidos com pelo menos 3 deputados. Governismo: mediana dos deputados do partido nas
          votações em que governo e oposição discordaram. Especialistas: Bolognesi, Ribeiro,
          Codato e Silva (onda de 2022). <Link href="/metodologia">Como é calculado</Link>
        </p>
      </section>
    </>
  );
}
