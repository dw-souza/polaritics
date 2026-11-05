import Link from "next/link";

export default function NaoEncontrado() {
  return (
    <div className="container">
      <section className="cartao">
        <h1>Página não encontrada</h1>
        <p>
          Não encontramos esta página. Se você procurava um deputado, ele pode não ter exercido
          mandato na legislatura atual.
        </p>
        <p>
          <Link href="/">Buscar deputados</Link> · <Link href="/partidos">Ver partidos</Link>
        </p>
      </section>
    </div>
  );
}
