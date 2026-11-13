// Câmara municipal inteira na régua 0–10: uma linha por vereador, com o intervalo de 90%, e os
// grupos de votação (metodologia municipal, M4.2) separados por um cabeçalho. Vereadores do
// mesmo grupo votam de forma indistinguível com os dados disponíveis.
import Link from "next/link";

import { INTERVALOS_FAIXAS, formatarNota, pos } from "@/lib/escala";
import type { PosicaoVereador } from "@/lib/municipal";

import estilos from "./ReguaCamara.module.css";

export function ReguaCamara({
  posicoes,
  hrefVereador,
  destaque,
}: {
  posicoes: PosicaoVereador[];
  hrefVereador: (id: string) => string;
  destaque?: string;
}) {
  const ordenadas = [...posicoes].sort((a, b) => a.posicao - b.posicao);
  const grupos = new Map<number, PosicaoVereador[]>();
  for (const p of ordenadas) grupos.set(p.grupo, [...(grupos.get(p.grupo) ?? []), p]);
  return (
    <figure className={estilos.figura}>
      <figcaption className="sr-only">
        Posição de cada vereador na escala de 0 a 10, em grupos de votação. Os valores estão na
        tabela abaixo.
      </figcaption>
      <div className={estilos.grade}>
        <div className={estilos.fundo} aria-hidden="true">
          {INTERVALOS_FAIXAS.map((f) => (
            <i key={f.rotulo} style={{ color: `var(--faixa-${f.indice})` }} />
          ))}
        </div>
        {[...grupos.entries()].map(([grupo, membros]) => (
          <div key={grupo} className={estilos.grupo}>
            <div className={estilos.cabGrupo}>
              <span className="rotulo">
                {membros.length === 1 ? "Vota sozinho neste ponto" : `${membros.length} votam de forma indistinguível`}
              </span>
            </div>
            {membros.map((p) => (
              <div
                key={p.id_vereador}
                className={`${estilos.linha} ${p.id_vereador === destaque ? estilos.destaque : ""}`}
              >
                <Link href={hrefVereador(p.id_vereador)} className={estilos.nome}>
                  {p.nome}
                  <span>{p.partido ?? "sem partido"}</span>
                </Link>
                <div className={estilos.trilha}>
                  <span
                    className={estilos.intervalo}
                    style={{ left: pos(p.nota_p05), width: `${(p.nota_p95 - p.nota_p05) * 10}%` }}
                    aria-hidden="true"
                  />
                  <span
                    className={estilos.ponto}
                    style={{ left: pos(p.nota) }}
                    title={`${p.nome}: ${formatarNota(p.nota)} (entre ${formatarNota(p.nota_p05)} e ${formatarNota(p.nota_p95)})`}
                  />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className={estilos.eixo} aria-hidden="true">
        {[0, 2, 4, 6, 8, 10].map((v) => (
          <span key={v} style={{ left: pos(v) }}>
            {v}
          </span>
        ))}
      </div>
    </figure>
  );
}
