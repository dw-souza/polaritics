import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Foto } from "@/components/Foto";
import {
  publicacaoAtual,
  rankingFidelidade,
  rankingGovernismo,
  type LinhaRanking,
} from "@/lib/dados";
import { UFS, formatarPctDecimal } from "@/lib/escala";

import estilos from "./rankings.module.css";

export const metadata: Metadata = { title: "Rankings" };

const RANKINGS = {
  governismo: {
    nome: "Governismo",
    titulo: "Quem mais acompanha o governo",
    valor: "Com o governo",
    unidade: "votações disputadas",
    nota: "Percentual de votos iguais à orientação do governo nas votações em que governo e oposição pediram votos diferentes. Governismo não é ideologia: mede o apoio ao governo do momento.",
  },
  fidelidade: {
    nome: "Fidelidade ao partido",
    titulo: "Quem mais vota com o próprio partido",
    valor: "Com a bancada",
    unidade: "votações",
    nota: "Percentual de votos iguais ao da maioria da própria bancada, considerando o partido na data de cada voto. Fidelidade alta não é virtude nem defeito: mostra o quanto o deputado vota em bloco.",
  },
} as const;
type Chave = keyof typeof RANKINGS;

export default function PaginaRankings(props: PageProps<"/rankings">) {
  return (
    <>
      <section className="cabeca-pagina">
        <h1>Rankings</h1>
        <p>
          Cada ranking é separado. Não existe nota geral: acompanhar o governo, votar com o
          partido e estar à esquerda ou à direita são coisas diferentes.
        </p>
      </section>
      <Suspense fallback={<p className="discreto">Carregando…</p>}>
        <Conteudo {...props} />
      </Suspense>
    </>
  );
}

function href(r: Chave, uf: string, partido: string) {
  const q = new URLSearchParams();
  if (r !== "governismo") q.set("r", r);
  if (uf) q.set("uf", uf);
  if (partido) q.set("partido", partido);
  const s = q.toString();
  return s ? `/rankings?${s}` : "/rankings";
}

async function Conteudo({ searchParams }: PageProps<"/rankings">) {
  const sp = await searchParams;
  const r: Chave = sp.r === "fidelidade" ? "fidelidade" : "governismo";
  const uf = typeof sp.uf === "string" ? sp.uf : "";
  const partido = typeof sp.partido === "string" ? sp.partido : "";
  const pub = await publicacaoAtual();
  if (!pub) return null;
  const todos =
    r === "governismo"
      ? await rankingGovernismo(pub.legislatura)
      : await rankingFidelidade(pub.legislatura);

  // posição geral (empates dividem a posição), calculada antes dos filtros
  const posicao = new Map<string, number>();
  for (const l of todos) posicao.set(l.id_camara, 1 + todos.filter((o) => o.valor > l.valor).length);
  const filtrados = todos.filter((l) => (!uf || l.uf === uf) && (!partido || l.partido === partido));
  const ufs = [...new Set(todos.map((l) => l.uf).filter(Boolean) as string[])].sort();
  const partidos = [...new Set(todos.map((l) => l.partido).filter(Boolean) as string[])].sort();
  const cfg = RANKINGS[r];
  const resumido = !uf && !partido && filtrados.length > 40;
  const linhas: (LinhaRanking | null)[] = resumido
    ? [...filtrados.slice(0, 20), null, ...filtrados.slice(-20)]
    : filtrados;

  return (
    <section className="secao">
      <div className={estilos.controles}>
        <nav className="seg" aria-label="Ranking">
          {(Object.keys(RANKINGS) as Chave[]).map((k) => (
            <Link key={k} href={href(k, uf, partido)} aria-current={k === r ? "true" : undefined}>
              {RANKINGS[k].nome}
            </Link>
          ))}
        </nav>
        <form className={estilos.filtros} action="/rankings">
          {r !== "governismo" && <input type="hidden" name="r" value={r} />}
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
                <th className="n">{cfg.valor}</th>
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
                        <i style={{ width: `${l.valor * 100}%` }} />
                      </span>
                    </td>
                    <td className="n">
                      <strong>{formatarPctDecimal(l.valor)}</strong>
                      <span className={estilos.sub}>
                        {l.n} {cfg.unidade}
                      </span>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
      <p className={estilos.nota}>
        {cfg.nota} Só entram deputados que votaram em pelo menos 10% das votações do período.
        Posição entre os {todos.length} com dados suficientes. Rankings de gastos da cota
        parlamentar, presença e atividade legislativa estão em preparação.
      </p>
    </section>
  );
}
