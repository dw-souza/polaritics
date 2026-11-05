// Régua compacta dos cartões: as 7 faixas e um ponto na nota.
import { pos } from "@/lib/escala";

import estilos from "./MiniRegua.module.css";

export function MiniRegua({ nota }: { nota: number }) {
  return (
    <div className={estilos.trilho} aria-hidden="true">
      {[1, 2, 3, 4, 5, 6, 7].map((i) => (
        <i key={i} style={{ background: `var(--faixa-${i})` }} />
      ))}
      <span className={estilos.ponto} style={{ left: pos(nota) }} />
    </div>
  );
}
