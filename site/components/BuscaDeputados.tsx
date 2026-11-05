"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import type { DeputadoResumo } from "@/lib/dados";
import { UFS, formatarNota } from "@/lib/escala";

import { Foto } from "./Foto";
import { MiniRegua } from "./MiniRegua";
import estilos from "./BuscaDeputados.module.css";

const normalizar = (s: string) =>
  s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export function BuscaDeputados({
  deputados,
  abertura,
  destaques,
}: {
  deputados: DeputadoResumo[];
  abertura: ReactNode;
  destaques?: ReactNode;
}) {
  const [termo, setTermo] = useState("");
  const [uf, setUf] = useState("");
  const ufs = useMemo(
    () => [...new Set(deputados.map((d) => d.uf).filter(Boolean) as string[])].sort(),
    [deputados],
  );
  const filtrados = useMemo(() => {
    const t = normalizar(termo.trim());
    return deputados.filter(
      (d) =>
        (!uf || d.uf === uf) &&
        (!t || normalizar(`${d.nome} ${d.partido ?? ""} ${d.uf ?? ""} ${UFS[d.uf ?? ""] ?? ""}`).includes(t)),
    );
  }, [termo, uf, deputados]);

  return (
    <>
      <section className={estilos.abertura}>
        <div>{abertura}</div>
        <div className={estilos.busca}>
        <label htmlFor="busca">Busque por nome, partido ou estado</label>
        <input
          id="busca"
          type="search"
          className={estilos.campo}
          placeholder="Ex.: Tabata, PSOL, Bahia"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          autoComplete="off"
        />
        <div className={estilos.ufs} role="group" aria-label="Filtrar por estado">
          <button type="button" aria-pressed={uf === ""} onClick={() => setUf("")}>
            Todos
          </button>
          {ufs.map((u) => (
            <button
              key={u}
              type="button"
              aria-pressed={uf === u}
              onClick={() => setUf(uf === u ? "" : u)}
              title={UFS[u]}
            >
              {u}
            </button>
          ))}
        </div>
        </div>
      </section>

      {destaques}

      <section className="secao" aria-labelledby="titulo-lista">
        <div className="secao-cab">
          <h2 id="titulo-lista">{uf ? `Deputados de ${UFS[uf] ?? uf}` : "Todos os deputados"}</h2>
          <span className="rotulo" aria-live="polite">
            {filtrados.length} {filtrados.length === 1 ? "deputado" : "deputados"}
          </span>
        </div>
        {filtrados.length === 0 ? (
          <p className="discreto">
            Ninguém encontrado. Confira a grafia ou tire o filtro de estado.
          </p>
        ) : (
          <ul className={estilos.grade}>
            {filtrados.map((d) => (
              <li key={d.id_camara}>
                <Link href={`/deputado/${d.id_camara}`} className={estilos.cartao}>
                  <Foto url={d.foto_url} nome={d.nome} />
                  <span className={estilos.nome}>{d.nome}</span>
                  <span className={estilos.meta}>
                    {[d.partido, d.uf].filter(Boolean).join(" · ")}
                  </span>
                  <span className={estilos.posicao}>
                    {d.nota !== null && d.faixa_exibida ? (
                      <>
                        <MiniRegua nota={d.nota} />
                        <span className={estilos.rodape}>
                          <span>{d.faixa_exibida}</span>
                          <span className="num">{formatarNota(d.nota)}</span>
                        </span>
                      </>
                    ) : (
                      <span className={estilos.rodape}>
                        <span className="discreto">Votos insuficientes para posição</span>
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
