// Régua 0–10 com as 7 faixas fixas e marcadores. Cada marcador mostra o valor ao passar o
// mouse ou ao receber foco; os mesmos valores aparecem em texto ao lado da régua, então a dica
// só complementa.
import { INTERVALOS_FAIXAS, formatarNota, pos } from "@/lib/escala";

import estilos from "./Regua.module.css";

export type Marcador = {
  rotulo: string;
  nota: number;
  intervalo?: [number, number];
  forma: "ponto" | "losango" | "anel";
  destaque?: boolean;
};

export function Regua({ marcadores, titulo }: { marcadores: Marcador[]; titulo: string }) {
  return (
    <figure className={estilos.figura}>
      <figcaption className="sr-only">{titulo}</figcaption>
      <div className={estilos.area}>
        <div className={estilos.faixas} aria-hidden="true">
          {INTERVALOS_FAIXAS.map((f) => (
            <div
              key={f.rotulo}
              className={estilos.faixa}
              style={
                {
                  left: pos(f.inicio),
                  width: `${((f.fim - f.inicio) / 10) * 100}%`,
                  "--cor": `var(--faixa-${f.indice})`,
                } as React.CSSProperties
              }
            />
          ))}
        </div>
        {marcadores.map((m) => (
          <div key={m.rotulo} className={estilos.camada}>
            {m.intervalo && (
              <div
                className={estilos.intervalo}
                style={{
                  left: pos(m.intervalo[0]),
                  width: `${((m.intervalo[1] - m.intervalo[0]) / 10) * 100}%`,
                }}
                aria-hidden="true"
              />
            )}
            <button
              type="button"
              className={`${estilos.marcador} ${estilos[m.forma]} ${m.destaque ? estilos.destaque : ""}`}
              style={{ left: pos(m.nota) }}
              aria-label={`${m.rotulo}: ${formatarNota(m.nota)}`}
            >
              <span className={estilos.dica} role="tooltip">
                <strong>{formatarNota(m.nota)}</strong>
                {m.intervalo && (
                  <span>
                    {" "}
                    ({formatarNota(m.intervalo[0])}–{formatarNota(m.intervalo[1])})
                  </span>
                )}
                <span className={estilos.dicaRotulo}>{m.rotulo}</span>
              </span>
            </button>
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
      <div className={estilos.extremos} aria-hidden="true">
        <span>← mais à esquerda</span>
        <span>mais à direita →</span>
      </div>
      <ul className={estilos.legenda}>
        {marcadores.map((m) => (
          <li key={m.rotulo}>
            <span className={`${estilos.chave} ${estilos[m.forma]}`} aria-hidden="true" />
            {m.rotulo}: <strong className="numeros">{formatarNota(m.nota)}</strong>
            {m.intervalo && (
              <span className="secundario">
                {" "}
                (intervalo de 90%: {formatarNota(m.intervalo[0])} a{" "}
                {formatarNota(m.intervalo[1])})
              </span>
            )}
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
          <span className="secundario numeros">
            ({formatarNota(f.inicio)}–{formatarNota(f.fim)})
          </span>
        </li>
      ))}
    </ul>
  );
}
