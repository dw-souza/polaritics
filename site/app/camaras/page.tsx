import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { URL_METODOLOGIA_MUNICIPAL, municipios } from "@/lib/municipal";

import estilos from "./camaras.module.css";

export const metadata: Metadata = { title: "Câmaras municipais" };

export default function PaginaCamaras() {
  return (
    <>
      <section className="cabeca-pagina">
        <h1>Câmaras municipais</h1>
        <p>
          O mesmo método aplicado aos vereadores, com as adaptações que uma câmara pequena exige.
          Em fase de teste, começando por uma cidade.
        </p>
      </section>
      <section className="secao">
        <Suspense fallback={<p className="discreto">Carregando…</p>}>
          <Lista />
        </Suspense>
        <p className="pequeno discreto leitura" style={{ marginTop: 20 }}>
          Numa câmara municipal, quase todas as votações são unânimes, os partidos têm poucos
          vereadores e não há orientação de governo registrada. Por isso a régua, o governismo e a
          validação seguem um anexo próprio da metodologia.{" "}
          <a href={URL_METODOLOGIA_MUNICIPAL}>Leia o anexo municipal</a>
        </p>
      </section>
    </>
  );
}

async function Lista() {
  const lista = await municipios();
  if (lista.length === 0) return <p className="discreto">Nenhuma câmara publicada ainda.</p>;
  return (
    <ul className={estilos.lista}>
      {lista.map((m) => (
        <li key={m.municipio}>
          <Link href={`/camaras/${m.municipio}`}>
            <strong>{m.nome}</strong>
            <span className="rotulo">{m.uf}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
