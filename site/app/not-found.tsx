import Link from "next/link";

export default function NaoEncontrado() {
  return (
    <section className="cabeca-pagina">
      <h1>Página não encontrada</h1>
      <p>
        Não encontramos esta página. Se você procurava um deputado, ele pode não ter exercido
        mandato na legislatura atual. <Link href="/">Buscar deputados</Link> ou{" "}
        <Link href="/partidos">ver os partidos</Link>.
      </p>
    </section>
  );
}
