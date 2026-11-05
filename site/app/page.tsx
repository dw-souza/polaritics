import Link from "next/link";

import { BuscaDeputados } from "@/components/BuscaDeputados";
import { LegendaFaixas } from "@/components/Regua";
import { listaDeputados, publicacaoAtual } from "@/lib/dados";

export default async function Inicio() {
  const pub = await publicacaoAtual();
  const deputados = pub ? await listaDeputados(pub.legislatura) : [];

  return (
    <div className="container">
      <section className="cartao">
        <h1>O que ele diz ser, e como ele vota</h1>
        <p>
          O Polaritics mostra onde cada deputado federal fica na escala política{" "}
          <strong>pelo jeito que vota</strong>, ao lado de como especialistas classificam o
          partido dele e do quanto ele acompanha o governo. Tudo a partir das votações nominais
          registradas pela Câmara.
        </p>
        <LegendaFaixas />
        <p className="secundario pequeno" style={{ marginTop: 12 }}>
          A posição é uma estimativa estatística, com margem de incerteza.{" "}
          <Link href="/metodologia">Entenda como funciona</Link>.
        </p>
      </section>
      <section className="cartao">
        <h2>Deputados federais</h2>
        <BuscaDeputados deputados={deputados} />
      </section>
    </div>
  );
}
