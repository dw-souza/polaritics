// Régua 0–10 com as 7 faixas fixas. Cada marcador ocupa uma linha, para não se sobreporem; os
// valores aparecem na dica (mouse ou foco) e também na legenda em texto, então a dica só
// complementa.
import { FAIXAS, INTERVALOS_FAIXAS, formatarNota, pos } from "@/lib/escala";

import estilos from "./Regua.module.css";

export type Marcador = {
  rotulo: string;
  nota: number;
  intervalo?: [number, number];
  forma: "ponto" | "losango" | "anel";
  detalhe?: string;
};

const ABREVIADO: Record<string, string> = {
  "Mais à esquerda": "Mais à esq.",
  "Centro-esquerda": "Centro-esq.",
  "Centro-direita": "Centro-dir.",
  "Mais à direita": "Mais à dir.",
};

export function Regua({ marcadores, titulo }: { marcadores: Marcador[]; titulo: string }) {
  return (
    <figure className={estilos.figura}>
      <figcaption className="sr-only">{titulo}</figcaption>
      <div className={estilos.area}>
        <div className={estilos.fundo} aria-hidden="true">
          {INTERVALOS_FAIXAS.map((f) => (
            <i key={f.rotulo} style={{ color: `var(--faixa-${f.indice})` }} />
          ))}
        </div>
        <div className={estilos.linhas}>
          {marcadores.map((m) => (
            <div key={m.rotulo} className={estilos.linha}>
              {m.intervalo && (
                <span
                  className={estilos.intervalo}
                  style={{
                    left: pos(m.intervalo[0]),
                    width: `${(m.intervalo[1] - m.intervalo[0]) * 10}%`,
                  }}
                  aria-hidden="true"
                />
              )}
              <button
                type="button"
                className={`${estilos.marcador} ${estilos[m.forma]}`}
                style={{ left: pos(m.nota) }}
                aria-label={`${m.rotulo}: ${formatarNota(m.nota)}`}
              >
                <span className={estilos.dica} role="tooltip">
                  <strong>{formatarNota(m.nota)}</strong>
                  {m.intervalo &&
                    ` (entre ${formatarNota(m.intervalo[0])} e ${formatarNota(m.intervalo[1])})`}
                  <span className={estilos.dicaRotulo}>{m.rotulo}</span>
                </span>
              </button>
            </div>
          ))}
        </div>
      </div>
      <div className={estilos.eixo} aria-hidden="true">
        {[0, 2, 4, 6, 8, 10].map((v) => (
          <span key={v} style={{ left: pos(v) }}>
            {v}
          </span>
        ))}
      </div>
      <div className={estilos.nomes} aria-hidden="true">
        {FAIXAS.map((f) => (
          <span key={f.rotulo}>{ABREVIADO[f.rotulo] ?? f.rotulo}</span>
        ))}
      </div>
      <ul className={estilos.legenda}>
        {marcadores.map((m) => (
          <li key={m.rotulo}>
            <span className={`${estilos.chave} ${estilos[m.forma]}`} aria-hidden="true" />
            {m.rotulo}:{" "}
            <strong className="num">
              {formatarNota(m.nota)}
              {m.intervalo &&
                ` (entre ${formatarNota(m.intervalo[0])} e ${formatarNota(m.intervalo[1])})`}
            </strong>
            {m.detalhe && <span className="discreto">{m.detalhe}</span>}
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function LegendaFaixas() {
  return (
    <ul className={estilos.legendaFaixas}>
      {INTERVALOS_FAIXAS.map((f) => (
        <li key={f.rotulo}>
          <span
            className={estilos.amostra}
            style={{ background: `var(--faixa-${f.indice})` }}
            aria-hidden="true"
          />
          {f.rotulo}{" "}
          <span className="discreto num">
            {formatarNota(f.inicio)}–{formatarNota(f.fim)}
          </span>
        </li>
      ))}
    </ul>
  );
}
