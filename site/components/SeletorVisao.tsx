// Seletor das visões (metodologia, 4.2.1). Cada opção é um link: a visão fica na URL, então um
// link compartilhado mostra a mesma visão, e a padrão não aparece na URL.
import Link from "next/link";

import { REGUAS, VOTACOES, hrefVisao, type Regua, type Votacoes } from "@/lib/escala";

import estilos from "./SeletorVisao.module.css";

export function SeletorVisao({
  base,
  regua,
  votacoes,
}: {
  base: string;
  regua: Regua;
  votacoes: Votacoes;
}) {
  return (
    <div className={estilos.seletor}>
      <div className={estilos.grupos}>
        <nav className="seg" aria-label="Régua">
          {(Object.keys(REGUAS) as Regua[]).map((r) => (
            <Link
              key={r}
              href={hrefVisao(base, r, votacoes)}
              aria-current={r === regua ? "true" : undefined}
              scroll={false}
            >
              {REGUAS[r].nome}
            </Link>
          ))}
        </nav>
        <nav className="seg" aria-label="Votações">
          {(Object.keys(VOTACOES) as Votacoes[]).map((v) => (
            <Link
              key={v}
              href={hrefVisao(base, regua, v)}
              aria-current={v === votacoes ? "true" : undefined}
              scroll={false}
            >
              {VOTACOES[v].nome}
            </Link>
          ))}
        </nav>
      </div>
      <p className={estilos.explicacao}>
        {REGUAS[regua].pergunta} {VOTACOES[votacoes].explicacao}
        {(regua !== "voto" || votacoes !== "todas") && (
          <>
            {" "}
            <Link href={hrefVisao(base, "voto", "todas")} scroll={false}>
              Voltar à visão padrão
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
