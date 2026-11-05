"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { DeputadoResumo } from "@/lib/dados";
import { FAIXAS, faixa, formatarNota } from "@/lib/escala";

import estilos from "./BuscaDeputados.module.css";

const normalizar = (s: string) =>
  s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

const indiceFaixa = (nota: number) => FAIXAS.findIndex((f) => f.rotulo === faixa(nota)) + 1;

export function BuscaDeputados({ deputados }: { deputados: DeputadoResumo[] }) {
  const [termo, setTermo] = useState("");
  const filtrados = useMemo(() => {
    const t = normalizar(termo.trim());
    if (!t) return deputados;
    return deputados.filter((d) =>
      normalizar(`${d.nome} ${d.partido ?? ""} ${d.uf ?? ""}`).includes(t),
    );
  }, [termo, deputados]);

  return (
    <div>
      <label htmlFor="busca" className={estilos.rotulo}>
        Buscar deputado, partido ou estado
      </label>
      <input
        id="busca"
        type="search"
        className={estilos.campo}
        placeholder="Ex.: Tabata, PL, BA"
        value={termo}
        onChange={(e) => setTermo(e.target.value)}
        autoComplete="off"
      />
      <p className={`secundario pequeno ${estilos.contagem}`} aria-live="polite">
        {filtrados.length} de {deputados.length} deputados
      </p>
      <ul className={estilos.lista}>
        {filtrados.map((d) => (
          <li key={d.id_camara}>
            <Link href={`/deputado/${d.id_camara}`} className={estilos.item}>
              <span className={estilos.nome}>{d.nome}</span>
              <span className="secundario pequeno">
                {[d.partido, d.uf].filter(Boolean).join(" · ")}
              </span>
              {d.nota !== null && d.faixa_exibida ? (
                <span className={estilos.faixa}>
                  <span
                    className={estilos.amostra}
                    style={{ background: `var(--faixa-${indiceFaixa(d.nota)})` }}
                    aria-hidden="true"
                  />
                  {d.faixa_exibida}{" "}
                  <span className="secundario numeros">{formatarNota(d.nota)}</span>
                </span>
              ) : (
                <span className={`secundario pequeno ${estilos.faixa}`}>dados insuficientes</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
