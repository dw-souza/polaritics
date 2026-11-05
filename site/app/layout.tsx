import type { Metadata } from "next";
import Link from "next/link";

import { publicacaoAtual } from "@/lib/dados";
import { formatarData } from "@/lib/escala";
import "./globals.css";
import estilos from "./layout.module.css";

export const metadata: Metadata = {
  title: { default: "Polaritics", template: "%s · Polaritics" },
  description:
    "Como os deputados federais votam e onde esse comportamento os coloca na escala política, com dados oficiais da Câmara.",
};

async function Rodape() {
  const pub = await publicacaoAtual();
  return (
    <footer className={estilos.rodape}>
      <div className="container">
        <p>
          Dados oficiais da Câmara dos Deputados (Dados Abertos).
          {pub && (
            <>
              {" "}
              Votações até {formatarData(pub.dados_ate)} · {pub.legislatura}ª legislatura ·
              metodologia v{pub.versao_metodologia}.
            </>
          )}
        </p>
        <p>
          Código aberto (MIT) e resultados sob CC BY 4.0 ·{" "}
          <a href="https://github.com/dw-souza/polaritics">github.com/dw-souza/polaritics</a>
        </p>
      </div>
    </footer>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR">
      <body>
        <header className={estilos.cabecalho}>
          <div className={`container ${estilos.barra}`}>
            <Link href="/" className={estilos.marca}>
              Polaritics
            </Link>
            <nav className={estilos.nav} aria-label="Principal">
              <Link href="/">Deputados</Link>
              <Link href="/partidos">Partidos</Link>
              <Link href="/metodologia">Como funciona</Link>
            </nav>
          </div>
        </header>
        <main className={estilos.principal}>{children}</main>
        <Rodape />
      </body>
    </html>
  );
}
