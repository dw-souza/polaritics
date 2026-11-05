import type { Metadata } from "next";
import { Archivo, Source_Serif_4 } from "next/font/google";
import Link from "next/link";

import { publicacaoAtual } from "@/lib/dados";
import { formatarData } from "@/lib/escala";
import "./globals.css";
import estilos from "./layout.module.css";

const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--fonte-archivo",
  display: "swap",
});
const serif = Source_Serif_4({
  subsets: ["latin"],
  axes: ["opsz"],
  style: ["normal", "italic"],
  variable: "--fonte-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Polaritics", template: "%s · Polaritics" },
  description:
    "Como cada deputado federal vota, quanto gasta da cota, se vai às sessões e onde fica na escala política. Só com dados oficiais da Câmara.",
};

async function Rodape() {
  const pub = await publicacaoAtual();
  return (
    <footer className={estilos.rodape}>
      <p>
        Fontes: Câmara dos Deputados (Dados Abertos). Classificação dos partidos: Bolognesi,
        Ribeiro, Codato e Silva (2022).
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
    </footer>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${archivo.variable} ${serif.variable}`}>
      <body>
        <div className="miolo">
          <header className={estilos.topo}>
            <Link href="/" className={estilos.nome}>
              Polaritics<span>votos, gastos e presença na Câmara</span>
            </Link>
            <nav className={estilos.abas} aria-label="Principal">
              <Link href="/">Deputados</Link>
              <Link href="/rankings">Rankings</Link>
              <Link href="/partidos">Partidos</Link>
              <Link href="/metodologia">Como funciona</Link>
            </nav>
          </header>
          <div className={estilos.regua} aria-hidden="true">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <i key={i} style={{ background: `var(--faixa-${i})` }} />
            ))}
          </div>
          <main>{children}</main>
          <Rodape />
        </div>
      </body>
    </html>
  );
}
