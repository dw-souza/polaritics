import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Foto } from "@/components/Foto";
import {
  publicacaoAtual,
  rankingAtividade,
  rankingFidelidade,
  rankingGastos,
  rankingGovernismo,
  rankingPresenca,
  type LinhaRanking,
} from "@/lib/dados";
import { UFS, formatarPctDecimal, formatarReaisCurto } from "@/lib/escala";

import estilos from "./rankings.module.css";

export const metadata: Metadata = { title: "Rankings" };

type Config = {
  nome: string;
  titulo: string;
  coluna: string;
  crescente: boolean; // true: o 1º é o menor valor
  carregar: (legislatura: number) => Promise<LinhaRanking[]>;
  valor: (l: LinhaRanking) => string;
  detalhe: (l: LinhaRanking) => string;
  nota: string;
};

const RANKINGS: Record<string, Config> = {
  presenca: {
    nome: "Presença",
    titulo: "Quem mais vai às sessões do plenário",
    coluna: "Presença",
    crescente: false,
    carregar: rankingPresenca,
    valor: (l) => formatarPctDecimal(l.valor),
    detalhe: (l) => `${l.extra} de ${l.n} sessões`,
    nota: "Presença registrada nas sessões deliberativas do plenário, contando só as sessões em que o deputado estava em exercício (licenças e suplências ficam de fora). Entram deputados com pelo menos 20 sessões.",
  },
  gastos: {
    nome: "Cota parlamentar",
    titulo: "Quem gasta menos da cota parlamentar",
    coluna: "Por mês",
    crescente: true,
    carregar: rankingGastos,
    valor: (l) => formatarReaisCurto(l.extra ?? 0),
    detalhe: (l) => `${l.n} meses de mandato · cota de ${l.uf}`,
    nota: "Média mensal de reembolsos da cota nos meses em exercício. A ordem compara o gasto com a cota de cada estado (Ato da Mesa 270/2023), porque a cota de Roraima é 40% maior que a do DF. Não inclui passagens aéreas emitidas pelo sistema da Câmara, que não estão nos dados abertos. Entram deputados com pelo menos 3 meses de mandato.",
  },
  governismo: {
    nome: "Governismo",
    titulo: "Quem mais acompanha o governo",
    coluna: "Com o governo",
    crescente: false,
    carregar: rankingGovernismo,
    valor: (l) => formatarPctDecimal(l.valor),
    detalhe: (l) => `${l.n} votações disputadas`,
    nota: "Percentual de votos iguais à orientação do governo nas votações em que governo e oposição pediram votos diferentes. Governismo não é ideologia: mede o apoio ao governo do momento. Entram deputados que votaram em pelo menos 10% das votações.",
  },
  fidelidade: {
    nome: "Fidelidade ao partido",
    titulo: "Quem mais vota com o próprio partido",
    coluna: "Com a bancada",
    crescente: false,
    carregar: rankingFidelidade,
    valor: (l) => formatarPctDecimal(l.valor),
    detalhe: (l) => `${l.n} votações`,
    nota: "Percentual de votos iguais ao da maioria da própria bancada, considerando o partido na data de cada voto. Fidelidade alta não é virtude nem defeito: mostra o quanto o deputado vota em bloco.",
  },
  atividade: {
    nome: "Projetos aprovados",
    titulo: "Quem mais teve projetos aprovados na Câmara",
    coluna: "Aprovados",
    crescente: false,
    carregar: rankingAtividade,
    valor: (l) => String(l.valor),
    detalhe: (l) =>
      `de ${l.n} apresentados${l.extra ? ` · ${l.extra} ${l.extra === 1 ? "virou lei" : "viraram lei"}` : ""}`,
    nota: "PL, PLP, PEC e PDL apresentados como autor principal nesta legislatura e aprovados na Câmara (seguiram para o Senado, para sanção ou viraram lei). Quantidade não é qualidade: o ranking mostra só os aprovados, e não o total apresentado.",
  },
};
const PADRAO = "presenca";

export default function PaginaRankings(props: PageProps<"/rankings">) {
  return (
    <>
      <section className="cabeca-pagina">
        <h1>Rankings</h1>
        <p>
          Cada ranking é separado. Não existe nota geral: ir às sessões, gastar pouco, acompanhar
          o governo e estar à esquerda ou à direita são coisas diferentes.
        </p>
      </section>
      <Suspense fallback={<p className="discreto">Carregando…</p>}>
        <Conteudo {...props} />
      </Suspense>
    </>
  );
}

function href(r: string, uf: string, partido: string) {
  const q = new URLSearchParams();
  if (r !== PADRAO) q.set("r", r);
  if (uf) q.set("uf", uf);
  if (partido) q.set("partido", partido);
  const s = q.toString();
  return s ? `/rankings?${s}` : "/rankings";
}

async function Conteudo({ searchParams }: PageProps<"/rankings">) {
  const sp = await searchParams;
  const r = typeof sp.r === "string" && sp.r in RANKINGS ? sp.r : PADRAO;
  const uf = typeof sp.uf === "string" ? sp.uf : "";
  const partido = typeof sp.partido === "string" ? sp.partido : "";
  const cfg = RANKINGS[r];
  const pub = await publicacaoAtual();
  if (!pub) return null;
  const todos = await cfg.carregar(pub.legislatura);

  // posição geral (empates dividem a posição), calculada antes dos filtros
  const melhor = (a: number, b: number) => (cfg.crescente ? a < b : a > b);
  const posicao = new Map<string, number>();
  for (const l of todos) {
    posicao.set(l.id_camara, 1 + todos.filter((o) => melhor(o.valor, l.valor)).length);
  }
  const filtrados = todos.filter(
    (l) => (!uf || l.uf === uf) && (!partido || l.partido === partido),
  );
  const ufs = [...new Set(todos.map((l) => l.uf).filter(Boolean) as string[])].sort();
  const partidos = [...new Set(todos.map((l) => l.partido).filter(Boolean) as string[])].sort();
  const maximo = Math.max(...todos.map((l) => l.valor), 1e-9);
  const resumido = !uf && !partido && filtrados.length > 40;
  const linhas: (LinhaRanking | null)[] = resumido
    ? [...filtrados.slice(0, 20), null, ...filtrados.slice(-20)]
    : filtrados;

  return (
    <section className="secao">
      <div className={estilos.controles}>
        <nav className="seg" aria-label="Ranking">
          {Object.entries(RANKINGS).map(([k, c]) => (
            <Link key={k} href={href(k, uf, partido)} aria-current={k === r ? "true" : undefined}>
              {c.nome}
            </Link>
          ))}
        </nav>
        <form className={estilos.filtros} action="/rankings">
          {r !== PADRAO && <input type="hidden" name="r" value={r} />}
          <label htmlFor="f-uf">
            Estado
            <select id="f-uf" name="uf" defaultValue={uf}>
              <option value="">Todos</option>
              {ufs.map((u) => (
                <option key={u} value={u}>
                  {UFS[u] ?? u}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="f-partido">
            Partido
            <select id="f-partido" name="partido" defaultValue={partido}>
              <option value="">Todos</option>
              {partidos.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <button type="submit">Filtrar</button>
          {(uf || partido) && <Link href={href(r, "", "")}>Limpar filtros</Link>}
        </form>
      </div>

      <h2 className={estilos.titulo}>
        {cfg.titulo}
        {(uf || partido) && (
          <span className="discreto">
            {" "}
            · {[uf && (UFS[uf] ?? uf), partido].filter(Boolean).join(" · ")}
          </span>
        )}
      </h2>
      {filtrados.length === 0 ? (
        <p className="discreto">Nenhum deputado com dados suficientes nesse filtro.</p>
      ) : (
        <div className="tabela-rolagem">
          <table>
            <thead>
              <tr>
                <th>Posição</th>
                <th>Deputado</th>
                <th className={estilos.colBarra} aria-hidden="true"></th>
                <th className="n">{cfg.coluna}</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l, i) =>
                l === null ? (
                  <tr key={`corte-${i}`}>
                    <td colSpan={4} className={estilos.corte}>
                      {filtrados.length - 40} deputados no meio da lista · filtre por estado ou
                      partido para ver todos
                    </td>
                  </tr>
                ) : (
                  <tr key={l.id_camara}>
                    <td className={estilos.posicao}>{posicao.get(l.id_camara)}º</td>
                    <td>
                      <Link href={`/deputado/${l.id_camara}`} className={estilos.dep}>
                        <Foto url={l.foto_url} nome={l.nome} tamanho={36} />
                        <span>
                          <strong>{l.nome}</strong>
                          <span className={estilos.sub}>
                            {[l.partido, l.uf].filter(Boolean).join(" · ")}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td className={estilos.colBarra} aria-hidden="true">
                      <span className={estilos.barra}>
                        <i style={{ width: `${Math.min(1, l.valor / maximo) * 100}%` }} />
                      </span>
                    </td>
                    <td className="n">
                      <strong>{cfg.valor(l)}</strong>
                      <span className={estilos.sub}>{cfg.detalhe(l)}</span>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
      <p className={estilos.nota}>
        {cfg.nota} Posição entre os {todos.length} deputados com dados suficientes.
      </p>
    </section>
  );
}
