import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { LegendaFaixas } from "@/components/Regua";
import { partidos, publicacaoAtual } from "@/lib/dados";
import {
  INTERVALOS_FAIXAS,
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
    <div className="container">
      <h1>Partidos: o que dizem ser e como votam</h1>
      <p className="secundario">
        Para cada partido com pelo menos 3 deputados: a classificação feita por especialistas
        em ciência política e a posição mediana da bancada pelos votos em plenário. A distância
        entre os dois mostra o quanto o comportamento de voto se afasta da classificação.
      </p>
      <Suspense fallback={<p className="secundario">Carregando…</p>}>
        <Conteudo {...props} />
      </Suspense>
    </div>
  );
}

async function Conteudo({ searchParams }: PageProps<"/partidos">) {
  const { votacoes } = lerVisao(await searchParams);
  const pub = await publicacaoAtual();
  const linhas = pub ? await partidos(pub.legislatura, votacoes) : [];

  return (
    <>
      <nav className={estilos.seletor} aria-label="Votações consideradas">
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

      <section className="cartao">
        <ul className={estilos.legenda}>
          <li>
            <span className={`${estilos.chave} ${estilos.esp}`} aria-hidden="true" /> Segundo
            especialistas
          </li>
          <li>
            <span className={`${estilos.chave} ${estilos.voto}`} aria-hidden="true" /> Pelos
            votos (mediana da bancada)
          </li>
        </ul>
        <div className={estilos.grafico} role="img" aria-label="Gráfico: posição dos partidos segundo especialistas e pelos votos. Os mesmos valores estão na tabela abaixo.">
          {linhas.map((l) => {
            const a = l.nota_especialistas ?? l.nota_votos;
            const [ini, fim] = a < l.nota_votos ? [a, l.nota_votos] : [l.nota_votos, a];
            return (
              <div key={l.partido} className={estilos.linha}>
                <span className={estilos.sigla}>{l.partido}</span>
                <div className={estilos.trilho}>
                  {INTERVALOS_FAIXAS.map((f) => (
                    <span
                      key={f.rotulo}
                      className={estilos.fundo}
                      style={
                        {
                          left: pos(f.inicio),
                          width: `${((f.fim - f.inicio) / 10) * 100}%`,
                          "--cor": `var(--faixa-${f.indice})`,
                        } as React.CSSProperties
                      }
                    />
                  ))}
                  {l.nota_especialistas !== null && (
                    <span
                      className={estilos.ligacao}
                      style={{ left: pos(ini), width: `${((fim - ini) / 10) * 100}%` }}
                    />
                  )}
                  {l.nota_especialistas !== null && (
                    <span
                      className={`${estilos.ponto} ${estilos.esp}`}
                      style={{ left: pos(l.nota_especialistas) }}
                      title={`${l.partido} segundo especialistas: ${formatarNota(l.nota_especialistas)}`}
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
        <LegendaFaixas />
      </section>

      <section className="cartao">
        <h2>Tabela</h2>
        <div className="tabela-rolagem">
          <table>
            <thead>
              <tr>
                <th>Partido</th>
                <th className="num">Deputados</th>
                <th>Segundo especialistas</th>
                <th>Pelos votos</th>
                <th className="num">Governismo*</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.partido}>
                  <td>{l.partido}</td>
                  <td className="num">{l.n_deputados}</td>
                  <td>
                    {l.nota_especialistas !== null
                      ? `${faixa(l.nota_especialistas)} (${formatarNota(l.nota_especialistas)})`
                      : "sem classificação"}
                  </td>
                  <td>
                    {l.faixa_votos} ({formatarNota(l.nota_votos)})
                  </td>
                  <td className="num">
                    {l.governismo_disputadas !== null ? formatarPct(l.governismo_disputadas) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="secundario pequeno" style={{ marginTop: 12 }}>
          * Mediana dos deputados do partido: percentual de votos com o governo nas votações em
          que governo e oposição discordaram. Classificação dos especialistas: Bolognesi, Ribeiro,
          Codato e Silva (onda de 2022). <Link href="/metodologia">Como é calculado</Link>
        </p>
      </section>
    </>
  );
}
