import type { Metadata } from "next";

import { LegendaFaixas } from "@/components/Regua";

export const metadata: Metadata = { title: "Como funciona" };

const DOC = "https://github.com/dw-souza/polaritics/blob/main/docs/metodologia.md";

export default function Metodologia() {
  return (
    <>
      <section className="cabeca-pagina">
      <h1>Como funciona</h1>
      <p>
        Resumo em linguagem simples. A metodologia completa, com todas as decisões, testes e
        limitações, está no <a href={DOC}>documento público do projeto</a>.
      </p>
      </section>

      <section className="secao leitura">
        <h2>De onde vêm os dados</h2>
        <p>
          Só de fontes oficiais: as <strong>votações nominais em plenário</strong> registradas
          pela Câmara dos Deputados (Dados Abertos). Votações simbólicas e secretas não têm voto
          individual e ficam de fora. Os dados são atualizados toda semana.
        </p>
        <p>
          Duas referências externas servem para calibrar e conferir os resultados, nunca para
          calculá-los: a classificação dos partidos feita por centenas de especialistas em
          ciência política (Bolognesi, Ribeiro, Codato e Silva, 2022) e a Pesquisa Legislativa
          Brasileira (Power e Zucco, 2021).
        </p>
      </section>

      <section className="secao leitura">
        <h2>Como a posição é calculada</h2>
        <p>
          Um modelo estatístico (teoria de resposta ao item) olha para <strong>quem vota junto
          com quem</strong> em mais de mil votações e encontra a posição de cada deputado numa
          linha. O modelo não sabe quem propôs cada projeto nem lê o conteúdo: uma votação em
          que esquerda e direita votam juntas quase não pesa.
        </p>
        <p>
          Para virar uma nota de 0 a 10, a linha é calibrada por dois partidos de referência, o
          maior de cada lado (hoje PT e PL), que recebem a nota dada pelos especialistas. Todos
          os outros partidos e deputados aparecem onde os votos os colocam.
        </p>
        <LegendaFaixas />
        <p className="pequeno discreto">
          As faixas têm cortes fixos. Ninguém é classificado nas pontas só por ser o mais à
          esquerda ou o mais à direita da Câmara.
        </p>
      </section>

      <section className="secao leitura">
        <h2>Incerteza e zona de fronteira</h2>
        <p>
          Toda posição tem um <strong>intervalo de 90%</strong>: a faixa onde o valor verdadeiro
          provavelmente está. Quando a nota fica muito perto do limite entre duas faixas, pequenas
          mudanças nas votações consideradas trocam o rótulo. Nesses casos mostramos as duas
          faixas (por exemplo, &ldquo;entre centro e centro-direita&rdquo;).
        </p>
        <p>
          Quem votou em menos de 10% das votações aparece como &ldquo;dados insuficientes&rdquo;.
        </p>
      </section>

      <section className="secao leitura">
        <h2>As visões</h2>
        <p>
          <strong>Comportamento de voto</strong> (padrão): onde o deputado está pelos votos, e se
          isso bate com o que o partido diz ser. <strong>Dentro do campo do partido</strong>:
          se ele vota de forma mais moderada ou mais radical que o próprio partido.
        </p>
        <p>
          <strong>Todas as votações</strong> (padrão) inclui as votações de andamento da pauta,
          como urgência e adiamento, em que o apoio ao governo pesa mais.{" "}
          <strong>Só mérito</strong> considera apenas o conteúdo dos projetos.
        </p>
        <p>
          A visão padrão é fixa e só muda com uma nova versão da metodologia, nunca conforme o
          resultado.
        </p>
      </section>

      <section className="secao leitura">
        <h2>Governismo não é ideologia</h2>
        <p>
          O governismo mede quanto o deputado acompanha a orientação do governo do momento. O
          número principal considera só as votações em que <strong>governo e oposição
          discordaram</strong>: votar &ldquo;com o governo&rdquo; numa pauta que a oposição também
          apoia é consenso, não apoio. Um partido de direita pode ter governismo alto num governo
          de esquerda, e é exatamente essa diferença que o Polaritics mostra.
        </p>
      </section>

      <section className="secao leitura">
        <h2>O que este site não mede</h2>
        <ul>
          <li>Discursos, projetos apresentados e atuação fora do plenário.</li>
          <li>Temas que a presidência da Câmara não colocou em votação.</li>
          <li>Votações simbólicas e secretas.</li>
        </ul>
        <p>
          Todos os resultados passam por testes automáticos antes de serem publicados, e o código
          é aberto: <a href="https://github.com/dw-souza/polaritics">github.com/dw-souza/polaritics</a>.
        </p>
      </section>
    </>
  );
}
