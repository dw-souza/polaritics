import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { Foto } from "@/components/Foto";
import { Regua, type Marcador } from "@/components/Regua";
import { SeletorVisao } from "@/components/SeletorVisao";
import {
  deputado,
  fidelidade,
  governismo,
  posicaoPartido,
  posicoes,
  publicacaoAtual,
  rankingFidelidade,
  rankingGovernismo,
  votacoesExplicativas,
  type Governismo as LinhaGovernismo,
  type LinhaRanking,
  type Posicao,
} from "@/lib/dados";
import {
  REGUAS,
  UFS,
  VOTACOES,
  cargo,
  ementaAtual,
  faixa,
  formatarDataCurta,
  formatarNota,
  formatarPct,
  fraseFaixa,
  lerVisao,
  nomeCurtoGoverno,
} from "@/lib/escala";

import estilos from "./pagina.module.css";

export default function PaginaDeputado(props: PageProps<"/deputado/[id]">) {
  return (
    <Suspense fallback={<p className="discreto">Carregando a ficha…</p>}>
      <Ficha {...props} />
    </Suspense>
  );
}

// Posição no ranking (1 = maior valor), com empates dividindo a mesma posição.
function colocacao(lista: LinhaRanking[], id: string) {
  const eu = lista.find((l) => l.id_camara === id);
  if (!eu) return null;
  return { posicao: 1 + lista.filter((l) => l.valor > eu.valor).length, total: lista.length };
}

async function Ficha({ params, searchParams }: PageProps<"/deputado/[id]">) {
  const { id } = await params;
  const { regua, votacoes } = lerVisao(await searchParams);
  const pub = await publicacaoAtual();
  if (!pub) notFound();
  const dep = await deputado(id, pub.legislatura);
  if (!dep) notFound();

  const [todas, gov, fid, partido, explicativas, rkGov, rkFid] = await Promise.all([
    posicoes(id, pub.legislatura),
    governismo(id, pub.legislatura),
    fidelidade(id, pub.legislatura),
    dep.partido ? posicaoPartido(dep.partido, pub.legislatura) : null,
    votacoesExplicativas(id, pub.legislatura, votacoes),
    rankingGovernismo(pub.legislatura),
    rankingFidelidade(pub.legislatura),
  ]);
  const posicao = todas.find((p) => p.regua === regua && p.variante === votacoes);
  const padrao = todas.find((p) => p.regua === "voto" && p.variante === "todas");
  const principal = todas.find((p) => p.regua === "voto" && p.variante === votacoes);
  const outra = todas.find((p) => p.regua === "voto" && p.variante !== votacoes);
  const govGeral = gov.find((g) => g.periodo === "legislatura" && g.suficiente);
  const fidGeral = fid.find((f) => f.periodo === "legislatura" && f.suficiente);
  const esp = partido?.especialistas ?? null;
  const bancada = partido?.votos.find((v) => v.variante === votacoes)?.nota_votos ?? null;
  const bancadaPadrao = partido?.votos.find((v) => v.variante === "todas")?.nota_votos ?? null;
  const posGov = colocacao(rkGov, id);
  const posFid = colocacao(rkFid, id);
  const ufNome = dep.uf ? (UFS[dep.uf] ?? dep.uf) : null;

  return (
    <article>
      <p className={estilos.migalha}>
        <Link href="/">← Todos os deputados</Link>
      </p>
      <header className={estilos.identidade}>
        <Foto url={dep.foto_url} nome={dep.nome} tamanho={104} />
        <div>
          <h1>{dep.nome}</h1>
          <p className={estilos.cargo}>
            {[cargo(dep.sexo), dep.partido, ufNome, `${pub.legislatura}ª legislatura`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </header>

      <Manchete posicao={padrao} partido={dep.partido} bancada={bancadaPadrao} gov={govGeral} />

      <section className={estilos.blocos} aria-label="Resumo">
        <div className={estilos.bloco}>
          <span className="rotulo">Posição pelos votos</span>
          {padrao ? (
            <>
              <span className={`${estilos.valor} num`}>
                {formatarNota(padrao.nota)} <small>{padrao.faixa_exibida.toLowerCase()}</small>
              </span>
              <span className={estilos.pos}>
                Entre {formatarNota(padrao.nota_p05)} e {formatarNota(padrao.nota_p95)}{" "}
                <span>(90% de certeza)</span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Votos insuficientes</span>
          )}
          <details>
            <summary>O que é</summary>
            Posição na escala de 0 (mais à esquerda) a 10 (mais à direita), estimada a partir das
            votações nominais em plenário.
          </details>
        </div>
        <div className={estilos.bloco}>
          <span className="rotulo">Governismo</span>
          {govGeral && govGeral.taxa_disputadas !== null ? (
            <>
              <span className={`${estilos.valor} num`}>
                {formatarPct(govGeral.taxa_disputadas)}
              </span>
              <span className={estilos.pos}>
                {posGov && `${posGov.posicao}º mais governista `}
                <span>
                  {posGov && `de ${posGov.total} · `}
                  {govGeral.n_disputadas} votações disputadas
                </span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Votos insuficientes</span>
          )}
          <details>
            <summary>O que é</summary>
            Percentual de votos iguais à orientação do governo quando governo e oposição pediram
            votos diferentes. Mede apoio ao governo do momento, não ideologia.
          </details>
        </div>
        <div className={estilos.bloco}>
          <span className="rotulo">Fidelidade ao partido</span>
          {fidGeral && fidGeral.taxa !== null ? (
            <>
              <span className={`${estilos.valor} num`}>{formatarPct(fidGeral.taxa)}</span>
              <span className={estilos.pos}>
                {posFid && `${posFid.posicao}º mais fiel `}
                <span>
                  {posFid && `de ${posFid.total} · `}
                  {fidGeral.n} votações
                </span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Votos insuficientes</span>
          )}
          <details>
            <summary>O que é</summary>
            Percentual de votos iguais ao da maioria da própria bancada, considerando o partido
            na data de cada voto.
          </details>
        </div>
      </section>

      <section className="secao">
        <div className="secao-cab">
          <h2>Onde {dep.sexo === "F" ? "ela" : "ele"} está na régua</h2>
        </div>
        <SeletorVisao base={`/deputado/${id}`} regua={regua} votacoes={votacoes} />
        {posicao ? (
          <div className={estilos.regua}>
            {posicao.fronteira && (
              <p className="aviso">
                <strong>Zona de fronteira.</strong> A nota fica muito perto do limite entre duas
                faixas: pequenas mudanças nas votações consideradas trocam o rótulo. Por isso
                mostramos as duas.
              </p>
            )}
            <Regua
              titulo={`Posição de ${dep.nome} na escala de 0 a 10`}
              marcadores={marcadoresDe(dep.nome, posicao, dep.partido, esp, bancada)}
            />
            <Comparacao
              nome={dep.nome}
              posicao={posicao}
              partido={dep.partido}
              esp={esp}
              bancada={bancada}
            />
            {principal && outra && principal.faixa_exibida !== outra.faixa_exibida && (
              <p className="pequeno discreto">
                A faixa depende das votações consideradas:{" "}
                {VOTACOES[principal.variante].nome.toLowerCase()} →{" "}
                {principal.faixa_exibida.toLowerCase()};{" "}
                {VOTACOES[outra.variante].nome.toLowerCase()} → {outra.faixa_exibida.toLowerCase()}.
              </p>
            )}
            <p className="pequeno discreto">
              Baseado em {posicao.n_votos} votos nominais em plenário · {REGUAS[posicao.regua].nome}{" "}
              · {VOTACOES[posicao.variante].nome} ·{" "}
              <Link href="/metodologia">como é calculado</Link>
            </p>
          </div>
        ) : (
          <p className="aviso">
            <strong>Votos insuficientes.</strong> {dep.nome} votou em menos de 10% das votações
            consideradas. Isso acontece com suplentes que exerceram pouco tempo, com quem ficou
            licenciado (por exemplo, para assumir um ministério ou secretaria) e com o presidente
            da Câmara, que normalmente não vota.
          </p>
        )}
      </section>

      {govGeral && <GovernismoPorAno linhas={gov} />}

      {posicao && explicativas.length > 0 && (
        <section className="secao">
          <div className="secao-cab">
            <h2>Votações que mais pesaram</h2>
            <span className="rotulo">Um item por projeto · {VOTACOES[votacoes].nome}</span>
          </div>
          <ol className={estilos.votos}>
            {explicativas.map((v) => (
              <li key={v.id_votacao}>
                <div>
                  <div className={estilos.pl}>
                    {v.proposicao && v.url_proposicao ? (
                      <a href={v.url_proposicao}>{v.proposicao}</a>
                    ) : (
                      "Votação"
                    )}
                  </div>
                  <div className={estilos.data}>
                    {formatarDataCurta(v.data)} ·{" "}
                    {v.tipo === "procedimento" ? "andamento da pauta" : "mérito"}
                  </div>
                </div>
                <div className="leitura">
                  {v.ementa && <p className={estilos.ementa}>{ementaAtual(v.ementa)}</p>}
                  <p className="pequeno discreto">
                    O que foi votado:{" "}
                    {v.descricao.replace(/\s*Sim:[\s\S]*$/i, "").trim() || v.descricao}
                  </p>
                  <p className="pequeno">
                    Votou <span className={estilos.voto}>{v.voto ?? "—"}</span>
                    <span className="discreto">
                      {" · "}
                      {v.orientacao_governo
                        ? `governo orientou ${v.orientacao_governo}`
                        : "governo não orientou"}
                      {" · "}
                      <a href={v.url}>registro oficial</a>
                    </span>
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  );
}

function Manchete({
  posicao,
  partido,
  bancada,
  gov,
}: {
  posicao: Posicao | undefined;
  partido: string | null;
  bancada: number | null;
  gov: LinhaGovernismo | undefined;
}) {
  if (!posicao && !gov) return null;
  const f = posicao ? fraseFaixa(posicao.faixa_exibida, posicao.fronteira) : null;
  let relacao = "";
  if (posicao && partido && bancada !== null) {
    relacao =
      bancada < posicao.nota_p05
        ? `, mais à direita que a bancada do ${partido}`
        : bancada > posicao.nota_p95
          ? `, mais à esquerda que a bancada do ${partido}`
          : `, em linha com o ${partido}`;
  }
  return (
    <p className={estilos.manchete}>
      {f && (
        <>
          {f.antes} <span className="marca">{f.destaque}</span>
          {relacao}
        </>
      )}
      {gov && gov.taxa_disputadas !== null && (
        <>
          {f ? ", e acompanha" : "Acompanha"} o governo {nomeCurtoGoverno(gov.governo)} em{" "}
          <span className="marca">{formatarPct(gov.taxa_disputadas)}</span> das votações em que
          governo e oposição discordaram
        </>
      )}
      .
    </p>
  );
}

function marcadoresDe(
  nome: string,
  posicao: Posicao,
  partido: string | null,
  esp: number | null,
  bancada: number | null,
): Marcador[] {
  const m: Marcador[] = [
    {
      rotulo: nome,
      nota: posicao.nota,
      intervalo: [posicao.nota_p05, posicao.nota_p95],
      forma: "ponto",
    },
  ];
  if (partido && esp !== null) {
    m.push({
      rotulo: `${partido} segundo especialistas`,
      nota: esp,
      forma: "losango",
      detalhe: faixa(esp).toLowerCase(),
    });
  }
  if (partido && bancada !== null && posicao.regua === "voto") {
    m.push({ rotulo: `Bancada do ${partido} pelos votos`, nota: bancada, forma: "anel" });
  }
  return m;
}

function Comparacao({
  nome,
  posicao,
  partido,
  esp,
  bancada,
}: {
  nome: string;
  posicao: Posicao;
  partido: string | null;
  esp: number | null;
  bancada: number | null;
}) {
  if (!partido) return null;
  if (esp === null) {
    return (
      <p className="leitura">
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
      <p className="leitura">
        Especialistas classificam o {partido} como {faixa(esp).toLowerCase()} (
        {formatarNota(esp)}). Comparado a essa referência, {nome} vota {lado(esp)} o partido.
      </p>
    );
  }
  return (
    <p className="leitura">
      Especialistas classificam o {partido} como <strong>{faixa(esp).toLowerCase()}</strong> (
      {formatarNota(esp)}).
      {bancada !== null && (
        <>
          {" "}
          Pelos votos, a bancada fica em <strong>{faixa(bancada).toLowerCase()}</strong> (
          {formatarNota(bancada)}), e {nome} vota {lado(bancada)} ela.
        </>
      )}
    </p>
  );
}

function GovernismoPorAno({ linhas }: { linhas: LinhaGovernismo[] }) {
  const anos = linhas.filter((l) => l.periodo !== "legislatura" && l.taxa_disputadas !== null);
  if (anos.length < 2) return null;
  return (
    <section className="secao">
      <div className="secao-cab">
        <h2>Governismo ano a ano</h2>
        <span className="rotulo">Votações em que governo e oposição discordaram</span>
      </div>
      <ul className={estilos.anos}>
        {anos.map((a) => (
          <li key={a.periodo}>
            <span className="num">{a.periodo}</span>
            <span className={estilos.trilho} aria-hidden="true">
              <i style={{ width: `${(a.taxa_disputadas ?? 0) * 100}%` }} />
            </span>
            <span className="num">
              <strong>{formatarPct(a.taxa_disputadas ?? 0)}</strong>{" "}
              <span className="discreto">de {a.n_disputadas}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
