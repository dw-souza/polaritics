import Link from "next/link";

import { BuscaDeputados } from "@/components/BuscaDeputados";
import { fatos, listaDeputados, publicacaoAtual } from "@/lib/dados";
import { faixa, formatarNota, formatarPct } from "@/lib/escala";

import estilos from "./inicio.module.css";

export default async function Inicio() {
  const pub = await publicacaoAtual();
  const [deputados, f] = pub
    ? await Promise.all([listaDeputados(pub.legislatura), fatos(pub.legislatura)])
    : [[], null];

  return (
    <BuscaDeputados
      deputados={deputados}
      abertura={
        <>
          <h1 className={estilos.titulo}>Quem é o seu deputado?</h1>
          <p className={estilos.lede}>
            Veja como ele vota, o quanto acompanha o governo e onde fica na escala política. Só
            com dados oficiais da Câmara.
          </p>
        </>
      }
      destaques={f && <Destaques f={f} />}
    />
  );
}

function Destaques({ f }: { f: NonNullable<Awaited<ReturnType<typeof fatos>>> }) {
  return (
    <section className="secao" aria-labelledby="titulo-fatos">
      <div className="secao-cab">
        <h2 id="titulo-fatos">O que os dados mostram</h2>
      </div>
      <div className={estilos.fatos}>
        {f.direita_especialistas !== null && f.direita_votos !== null && (
          <Link href="/partidos" className={estilos.fato}>
            <span className="rotulo">Partidos</span>
            <span className={estilos.grande}>
              <span className="marca">
                {formatarNota(f.direita_especialistas)} → {formatarNota(f.direita_votos)}
              </span>
            </span>
            <span className="pequeno discreto">
              Partidos que especialistas classificam como direita (
              {f.partidos_direita.slice(0, 3).join(", ")} e outros) votam, na mediana, como{" "}
              {faixa(f.direita_votos).toLowerCase()}.
            </span>
          </Link>
        )}
        {f.governismo_mediano !== null && (
          <Link href="/rankings" className={estilos.fato}>
            <span className="rotulo">Governismo</span>
            <span className={estilos.grande}>
              <span className="marca">{formatarPct(f.governismo_mediano)}</span>
            </span>
            <span className="pequeno discreto">
              Metade dos deputados acompanha o governo em pelo menos esta parte das votações em
              que governo e oposição discordaram.
            </span>
          </Link>
        )}
        {f.com_posicao > 0 && (
          <Link href="/metodologia" className={estilos.fato}>
            <span className="rotulo">Zona de fronteira</span>
            <span className={estilos.grande}>
              <span className="marca">{f.em_fronteira}</span>
            </span>
            <span className="pequeno discreto">
              de {f.com_posicao} deputados ficam tão perto do limite entre duas faixas que mostramos
              as duas, em vez de forçar um rótulo.
            </span>
          </Link>
        )}
      </div>
    </section>
  );
}
