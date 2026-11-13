import type { Metadata } from "next";

import { LegendaFaixas } from "@/components/Regua";
import { URL_METODOLOGIA_MUNICIPAL } from "@/lib/municipal";

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
        <h2>Sobre o projeto</h2>
        <p>
          O Polaritics é um projeto independente, sem vínculo partidário, em fase inicial. Foi
          construído com ajuda de inteligência artificial, no código e na análise dos dados, e as
          decisões de método foram tomadas e revisadas por uma pessoa. Ainda não tem domínio
          próprio. Todas as informações vêm de fontes públicas, a metodologia está descrita no
          documento público e o código é aberto.
        </p>
        <p>
          Os resultados não são ajustados a pedido de nenhum parlamentar ou partido. Erros nos
          dados podem ser apontados no repositório do projeto, e toda correção é documentada.
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
        <h2>Presença, gastos e projetos</h2>
        <p>
          Todas essas medidas consideram só o tempo em que o deputado estava de fato no mandato,
          segundo o histórico oficial de posse, licença e reassunção. Suplentes e quem se
          licenciou para ser ministro, por exemplo, não são comparados pelos quatro anos.
        </p>
        <p>
          <strong>Presença:</strong> sessões deliberativas do plenário com presença registrada,
          entre as que aconteceram enquanto o deputado estava em exercício.
        </p>
        <p>
          <strong>Cota parlamentar:</strong> média mensal de reembolsos. Como a cota de cada
          estado tem um valor diferente (a de Roraima é 40% maior que a do DF, por causa das
          passagens), a comparação nacional leva em conta a cota do estado, e a ficha mostra
          também a posição entre os deputados do mesmo estado. As passagens aéreas emitidas pelo
          sistema da própria Câmara não são publicadas nos dados abertos e ficam de fora.
          Fornecedores pessoa física aparecem sem nome.
        </p>
        <p>
          <strong>Projetos:</strong> PL, PLP, PEC e PDL apresentados como autor principal, e
          quantos foram aprovados na Câmara ou viraram lei. Quantidade não é qualidade, por isso o
          ranking é de projetos aprovados.
        </p>
      </section>

      <section className="secao leitura">
        <h2>Câmaras municipais</h2>
        <p>
          O mesmo modelo é aplicado aos vereadores, com os dados do sistema de cada câmara (SAPL).
          Três coisas mudam, porque uma câmara municipal é pequena e quase sempre vota por
          unanimidade:
        </p>
        <ul>
          <li>
            <strong>A régua</strong> é calibrada por todos os vereadores de partidos que
            especialistas classificam como de esquerda e de direita, e não por um partido de cada
            lado, que na câmara costuma ter um ou dois vereadores.
          </li>
          <li>
            <strong>Os grupos de votação</strong> mostram quem vota de forma indistinguível: com
            poucas votações divergentes, muitas posições se sobrepõem, e a página diz isso em vez de
            fingir precisão.
          </li>
          <li>
            <strong>O governismo</strong> é medido pelo voto nos projetos do prefeito, porque a
            câmara não registra orientação de governo.
          </li>
        </ul>
        <p>
          Moções sobre política nacional entram no cálculo e muitas vezes são as votações que mais
          separam os vereadores. Os detalhes estão no{" "}
          <a href={URL_METODOLOGIA_MUNICIPAL}>anexo municipal da metodologia</a>.
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
