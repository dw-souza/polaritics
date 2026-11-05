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
      <fieldset className={estilos.grupo}>
        <legend>Régua</legend>
        {(Object.keys(REGUAS) as Regua[]).map((r) => (
          <Link
            key={r}
            href={hrefVisao(base, r, votacoes)}
            className={estilos.opcao}
            aria-current={r === regua ? "true" : undefined}
            scroll={false}
          >
            {REGUAS[r].nome}
            {r === "voto" && <span className={estilos.padrao}> (padrão)</span>}
          </Link>
        ))}
      </fieldset>
      <fieldset className={estilos.grupo}>
        <legend>Votações</legend>
        {(Object.keys(VOTACOES) as Votacoes[]).map((v) => (
          <Link
            key={v}
            href={hrefVisao(base, regua, v)}
            className={estilos.opcao}
            aria-current={v === votacoes ? "true" : undefined}
            scroll={false}
          >
            {VOTACOES[v].nome}
            {v === "todas" && <span className={estilos.padrao}> (padrão)</span>}
          </Link>
        ))}
      </fieldset>
      <p className={`secundario pequeno ${estilos.explicacao}`}>
        <strong>{REGUAS[regua].nome}:</strong> {REGUAS[regua].pergunta}{" "}
        <strong>{VOTACOES[votacoes].nome}:</strong> {VOTACOES[votacoes].explicacao}
      </p>
    </div>
  );
}
