import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { LegendaFaixas, Regua, type Marcador } from "@/components/Regua";
import { SeletorVisao } from "@/components/SeletorVisao";
import {
  deputado,
  fidelidade,
  governismo,
  posicaoPartido,
  posicoes,
  publicacaoAtual,
  votacoesExplicativas,
  type Posicao,
} from "@/lib/dados";
import {
  REGUAS,
  VOTACOES,
  faixa,
  formatarDataCurta,
  formatarNota,
  formatarPct,
  lerVisao,
} from "@/lib/escala";

import estilos from "./pagina.module.css";

export default function PaginaDeputado(props: PageProps<"/deputado/[id]">) {
  return (
    <div className="container">
      <Suspense fallback={<p className="secundario">Carregando…</p>}>
        <Conteudo {...props} />
      </Suspense>
    </div>
  );
}

async function Conteudo({ params, searchParams }: PageProps<"/deputado/[id]">) {
  const { id } = await params;
  const { regua, votacoes } = lerVisao(await searchParams);
  const pub = await publicacaoAtual();
  if (!pub) notFound();
  const dep = await deputado(id, pub.legislatura);
  if (!dep) notFound();

  const [todas, gov, fid, partido, explicativas] = await Promise.all([
    posicoes(id, pub.legislatura),
    governismo(id, pub.legislatura),
    fidelidade(id, pub.legislatura),
    dep.partido ? posicaoPartido(dep.partido, pub.legislatura) : null,
    votacoesExplicativas(id, pub.legislatura, votacoes),
  ]);
  const posicao = todas.find((p) => p.regua === regua && p.variante === votacoes);
  const outraVariante = todas.find(
    (p) => p.regua === "voto" && p.variante !== votacoes,
  );
  const principal = todas.find((p) => p.regua === "voto" && p.variante === votacoes);

  return (
    <article>
      <header className={estilos.cabecalho}>
        {/* eslint-disable-next-line @next/next/no-img-element -- foto oficial da Câmara */}
        <img src={dep.foto_url} alt="" className={estilos.foto} width={88} height={116} />
        <div>
          <p className="secundario pequeno">
            <Link href="/">← Deputados</Link>
          </p>
          <h1>{dep.nome}</h1>
          <p className="secundario">
            Deputado(a) federal · {[dep.partido, dep.uf].filter(Boolean).join(" · ")} ·{" "}
            {pub.legislatura}ª legislatura
          </p>
        </div>
      </header>

      <section className="cartao">
        <h2>Posição na escala política</h2>
        <SeletorVisao base={`/deputado/${id}`} regua={regua} votacoes={votacoes} />
        {posicao ? (
          <Posicionamento
            nome={dep.nome}
            posicao={posicao}
            principal={principal}
            outraVariante={outraVariante}
            partido={dep.partido}
            dadosPartido={partido}
          />
        ) : (
          <DadosInsuficientes />
        )}
      </section>

      <section className="cartao">
        <h2>Governismo</h2>
        <Governismo linhas={gov} />
      </section>

      <section className="cartao">
        <h2>Fidelidade ao partido</h2>
        <Fidelidade linhas={fid} partido={dep.partido} />
      </section>

      {posicao && explicativas.length > 0 && (
        <section className="cartao">
          <h2>Votações que mais pesaram na posição</h2>
          <p className="secundario pequeno">
            Os votos que mais empurraram {dep.nome} para o lado em que está, considerando{" "}
            {VOTACOES[votacoes].nome.toLowerCase()}. Um item por projeto.
          </p>
          <ol className={estilos.votacoes}>
            {explicativas.map((v) => (
              <li key={v.id_votacao}>
                <p className={estilos.votacaoTitulo}>
                  {v.proposicao && v.url_proposicao ? (
                    <a href={v.url_proposicao}>{v.proposicao}</a>
                  ) : (
                    "Votação"
                  )}{" "}
                  <span className={estilos.etiqueta}>
                    {v.tipo === "procedimento" ? "andamento da pauta" : "mérito"}
                  </span>{" "}
                  <span className="secundario pequeno numeros">{formatarDataCurta(v.data)}</span>
                </p>
                {v.ementa && <p className={estilos.ementa}>{v.ementa}</p>}
                <p className="secundario pequeno">
                  O que foi votado: {v.descricao.replace(/\s*Sim:[\s\S]*$/i, "").trim() || v.descricao}
                </p>
                <p className="pequeno">
                  Voto: <strong>{v.voto ?? "—"}</strong>
                  {v.orientacao_governo && (
                    <span className="secundario"> · orientação do governo: {v.orientacao_governo}</span>
                  )}{" "}
                  · <a href={v.url}>registro oficial</a>
                </p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  );
}

function Posicionamento({
  nome,
  posicao,
  principal,
  outraVariante,
  partido,
  dadosPartido,
}: {
  nome: string;
  posicao: Posicao;
  principal: Posicao | undefined;
  outraVariante: Posicao | undefined;
  partido: string | null;
  dadosPartido: Awaited<ReturnType<typeof posicaoPartido>> | null;
}) {
  const esp = dadosPartido?.especialistas ?? null;
  const votosPartido = dadosPartido?.votos.find((v) => v.variante === posicao.variante);
  const marcadores: Marcador[] = [
    {
      rotulo: nome,
      nota: posicao.nota,
      intervalo: [posicao.nota_p05, posicao.nota_p95],
      forma: "ponto",
      destaque: true,
    },
  ];
  if (partido && esp !== null) {
    marcadores.push({ rotulo: `${partido} segundo especialistas`, nota: esp, forma: "losango" });
  }
  if (partido && votosPartido && posicao.regua === "voto") {
    marcadores.push({
      rotulo: `${partido} pelos votos (mediana da bancada)`,
      nota: votosPartido.nota_votos,
      forma: "anel",
    });
  }

  return (
    <>
      <p className={estilos.resumo}>
        {posicao.regua === "voto" ? "Pelos votos, " : "Comparado ao próprio partido, "}
        {nome} está{" "}
        {posicao.fronteira ? (
          <>
            entre as faixas{" "}
            <strong>{posicao.faixa_exibida.replace(/^Entre /, "")}</strong>
          </>
        ) : (
          <>
            na faixa <strong>{posicao.faixa_exibida}</strong>
          </>
        )}{" "}
        <span className="numeros">({formatarNota(posicao.nota)})</span>.
      </p>
      {posicao.fronteira && (
        <p className="aviso pequeno">
          <strong>Zona de fronteira.</strong> A nota fica muito perto do limite entre duas faixas:
          pequenas mudanças nas votações consideradas trocam o rótulo. Por isso mostramos as duas.
        </p>
      )}
      <Regua marcadores={marcadores} titulo={`Posição de ${nome} na escala de 0 a 10`} />
      <div className={estilos.faixas}>
        <LegendaFaixas />
      </div>
      <Comparacao
        nome={nome}
        posicao={posicao}
        partido={partido}
        esp={esp}
        votosPartido={votosPartido?.nota_votos ?? null}
      />
      {principal && outraVariante && principal.faixa_exibida !== outraVariante.faixa_exibida && (
        <p className="secundario pequeno">
          A faixa depende das votações consideradas: {VOTACOES[principal.variante].nome.toLowerCase()}{" "}
          → {principal.faixa_exibida.toLowerCase()};{" "}
          {VOTACOES[outraVariante.variante].nome.toLowerCase()} →{" "}
          {outraVariante.faixa_exibida.toLowerCase()}.
        </p>
      )}
      <p className="secundario pequeno">
        Baseado em {posicao.n_votos} votos nominais em plenário. Visão: {REGUAS[posicao.regua].nome}{" "}
        · {VOTACOES[posicao.variante].nome}. <Link href="/metodologia">Como é calculado</Link>
      </p>
    </>
  );
}

function Comparacao({
  nome,
  posicao,
  partido,
  esp,
  votosPartido,
}: {
  nome: string;
  posicao: Posicao;
  partido: string | null;
  esp: number | null;
  votosPartido: number | null;
}) {
  if (!partido) return null;
  if (esp === null) {
    return (
      <p>
        O partido {partido} não tem classificação de especialistas (foi criado ou fundido depois
        do levantamento), então só a posição pelos votos é mostrada.
      </p>
    );
  }
  // "Diferente" só quando a referência fica fora do intervalo de 90% do deputado.
  const lado = (ref: number) =>
    ref < posicao.nota_p05
      ? "mais à direita do que"
      : ref > posicao.nota_p95
        ? "mais à esquerda do que"
        : "em linha com";
  if (posicao.regua === "campo") {
    return (
      <p>
        Especialistas classificam o {partido} como {faixa(esp).toLowerCase()} (
        {formatarNota(esp)}). {nome} vota {lado(esp)} o partido.
      </p>
    );
  }
  return (
    <p>
      Especialistas classificam o {partido} como <strong>{faixa(esp).toLowerCase()}</strong> (
      {formatarNota(esp)}).
      {votosPartido !== null && (
        <>
          {" "}
          Pelos votos, a bancada do partido fica em{" "}
          <strong>{faixa(votosPartido).toLowerCase()}</strong> ({formatarNota(votosPartido)}), e{" "}
          {nome} vota {lado(votosPartido)} a bancada.
        </>
      )}
    </p>
  );
}

function DadosInsuficientes() {
  return (
    <p className="aviso">
      <strong>Dados insuficientes.</strong> Este parlamentar votou em menos de 10% das votações
      consideradas. Isso acontece com suplentes que exerceram pouco tempo, com quem ficou
      licenciado (por exemplo, para assumir um ministério ou secretaria) e com o presidente da
      Câmara, que normalmente não vota.
    </p>
  );
}

function Governismo({ linhas }: { linhas: Awaited<ReturnType<typeof governismo>> }) {
  const geral = linhas.find((l) => l.periodo === "legislatura");
  if (!geral || !geral.suficiente || geral.taxa_disputadas === null) {
    return <p className="secundario">Dados insuficientes para calcular o governismo.</p>;
  }
  const anos = linhas.filter((l) => l.periodo !== "legislatura" && l.taxa_disputadas !== null);
  return (
    <>
      <p className={estilos.numeroGrande}>{formatarPct(geral.taxa_disputadas)}</p>
      <p>
        dos votos acompanharam a orientação do governo ({geral.governo}) nas{" "}
        <strong>{geral.n_disputadas} votações em que governo e oposição discordaram</strong>.
        Considerando todas as votações em que o governo orientou, foram{" "}
        {formatarPct(geral.taxa_total ?? 0)} ({geral.n_total}).
      </p>
      <p className="secundario pequeno">
        Governismo não é ideologia: mede o apoio ao governo do momento. Votações de consenso
        (quando governo e oposição pedem o mesmo voto) ficam de fora do número principal.
      </p>
      {anos.length > 1 && (
        <div className="tabela-rolagem">
          <table>
            <caption className="sr-only">Governismo por ano</caption>
            <thead>
              <tr>
                <th>Ano</th>
                <th className="num">Votações disputadas</th>
                <th className="num">Com o governo</th>
              </tr>
            </thead>
            <tbody>
              {anos.map((a) => (
                <tr key={a.periodo}>
                  <td>{a.periodo}</td>
                  <td className="num">{a.n_disputadas}</td>
                  <td className="num">{formatarPct(a.taxa_disputadas ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Fidelidade({
  linhas,
  partido,
}: {
  linhas: Awaited<ReturnType<typeof fidelidade>>;
  partido: string | null;
}) {
  const geral = linhas.find((l) => l.periodo === "legislatura");
  if (!geral || !geral.suficiente || geral.taxa === null) {
    return <p className="secundario">Dados insuficientes para calcular a fidelidade.</p>;
  }
  return (
    <p>
      Votou igual à maioria da própria bancada em <strong>{formatarPct(geral.taxa)}</strong> das{" "}
      {geral.n} votações comparáveis
      {partido ? ` (partido na data de cada voto; hoje ${partido})` : ""}.
    </p>
  );
}
