import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { Foto } from "@/components/Foto";
import { Regua, type Marcador } from "@/components/Regua";
import { SeletorVisao } from "@/components/SeletorVisao";
import {
  atividade,
  deputado,
  fidelidade,
  gastos,
  governismo,
  posicaoPartido,
  posicoes,
  presenca,
  publicacaoAtual,
  rankingFidelidade,
  rankingGastos,
  rankingGovernismo,
  rankingPresenca,
  votacoesExplicativas,
  type Atividade,
  type Fidelidade as LinhaFidelidade,
  type Governismo as LinhaGovernismo,
  type Posicao,
} from "@/lib/dados";
import {
  REGUAS,
  UFS,
  VOTACOES,
  cargo,
  colocacao,
  ementaAtual,
  faixa,
  formatarDataCurta,
  formatarNota,
  formatarPct,
  formatarReais,
  formatarReaisCurto,
  fraseFaixa,
  lerVisao,
  nomeCategoria,
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

async function Ficha({ params, searchParams }: PageProps<"/deputado/[id]">) {
  const { id } = await params;
  const { regua, votacoes } = lerVisao(await searchParams);
  const pub = await publicacaoAtual();
  if (!pub) notFound();
  const dep = await deputado(id, pub.legislatura);
  if (!dep) notFound();

  const [todas, gov, fid, partido, explicativas, rkGov, rkFid, gst, pres, atv, rkGst, rkPres] =
    await Promise.all([
      posicoes(id, pub.legislatura),
      governismo(id, pub.legislatura),
      fidelidade(id, pub.legislatura),
      dep.partido ? posicaoPartido(dep.partido, pub.legislatura) : null,
      votacoesExplicativas(id, pub.legislatura, votacoes),
      rankingGovernismo(pub.legislatura),
      rankingFidelidade(pub.legislatura),
      gastos(id, pub.legislatura),
      presenca(id, pub.legislatura),
      atividade(id, pub.legislatura),
      rankingGastos(pub.legislatura),
      rankingPresenca(pub.legislatura),
    ]);
  const posicao = todas.find((p) => p.regua === regua && p.variante === votacoes);
  const padrao = todas.find((p) => p.regua === "voto" && p.variante === "todas");
  const principal = todas.find((p) => p.regua === "voto" && p.variante === votacoes);
  const outra = todas.find((p) => p.regua === "voto" && p.variante !== votacoes);
  const govGeral = gov.find((g) => g.periodo === "legislatura" && g.suficiente);
  const esp = partido?.especialistas ?? null;
  const bancada = partido?.votos.find((v) => v.variante === votacoes)?.nota_votos ?? null;
  const bancadaPadrao = partido?.votos.find((v) => v.variante === "todas")?.nota_votos ?? null;
  const posGov = colocacao(rkGov, id);
  const posFid = colocacao(rkFid, id);
  const posGst = colocacao(rkGst, id, true);
  const posPres = colocacao(rkPres, id);
  const gstGeral = gst.periodos.find((g) => g.periodo === "legislatura" && g.suficiente);
  const presGeral = pres.find((p) => p.periodo === "legislatura" && p.suficiente);
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
          <span className="rotulo">Presença no plenário</span>
          {presGeral ? (
            <>
              <span className={`${estilos.valor} num`}>{formatarPct(presGeral.taxa)}</span>
              <span className={estilos.pos}>
                {posPres && `${posPres.posicao}º de ${posPres.total} `}
                <span>
                  {posPres && `· ${posPres.posicaoUf}º de ${posPres.totalUf} em ${posPres.uf}`}
                </span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Sessões insuficientes</span>
          )}
          <details>
            <summary>O que é</summary>
            {presGeral
              ? `Presença registrada em ${presGeral.presentes} das ${presGeral.sessoes} sessões deliberativas do plenário em que estava em exercício.`
              : "Presença nas sessões deliberativas do plenário, contando só o tempo em exercício."}
          </details>
        </div>
        <div className={estilos.bloco}>
          <span className="rotulo">Cota parlamentar</span>
          {gstGeral && gstGeral.por_mes !== null ? (
            <>
              <span className={`${estilos.valor} num`}>
                {formatarReaisCurto(gstGeral.por_mes)}
                <small>/mês</small>
              </span>
              <span className={estilos.pos}>
                {posGst && `${posGst.posicaoUf}º de ${posGst.totalUf} em ${posGst.uf} `}
                <span>{posGst && `· ${posGst.posicao}º de ${posGst.total} no país`}</span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Tempo de mandato insuficiente</span>
          )}
          <details>
            <summary>O que é</summary>
            Média mensal de reembolsos da cota em exercício. O 1º lugar é quem gasta menos. A
            posição no país compara com a cota de cada estado. Não inclui passagens aéreas
            emitidas pela própria Câmara, que não estão nos dados abertos.
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

      <section className={`secao ${estilos.duas}`}>
        <CotaDetalhe gastos={gst} uf={dep.uf} />
        <MandatoDetalhe atividade={atv} fidelidade={fid} posFid={posFid} sexo={dep.sexo} />
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

function CotaDetalhe({
  gastos: g,
  uf,
}: {
  gastos: Awaited<ReturnType<typeof gastos>>;
  uf: string | null;
}) {
  const geral = g.periodos.find((p) => p.periodo === "legislatura");
  if (!geral || geral.total === 0) {
    return (
      <div>
        <div className="secao-cab">
          <h2>Como gasta a cota</h2>
        </div>
        <p className="leitura">
          {geral && geral.meses >= 1
            ? "Não pediu reembolso da cota parlamentar nesta legislatura."
            : "Sem gastos da cota registrados nesta legislatura."}
        </p>
      </div>
    );
  }
  const maior = g.categorias[0]?.valor ?? 1;
  return (
    <div>
      <div className="secao-cab">
        <h2>Como gasta a cota</h2>
      </div>
      <p className="pequeno discreto">
        {formatarReais(geral.total)} em reembolsos em {Math.round(geral.meses)} meses de
        mandato{uf ? `, pela cota de ${UFS[uf] ?? uf}` : ""}. Por categoria:
      </p>
      <ul className={estilos.barras}>
        {g.categorias.slice(0, 8).map((c) => (
          <li key={c.categoria}>
            <span>{nomeCategoria(c.categoria)}</span>
            <span className={estilos.trilhoBarra} aria-hidden="true">
              <i style={{ width: `${(c.valor / maior) * 100}%` }} />
            </span>
            <span className="num">{formatarReais(c.valor)}</span>
          </li>
        ))}
      </ul>
      {g.fornecedores.length > 0 && (
        <p className="pequeno discreto">
          Maiores fornecedores:{" "}
          {g.fornecedores
            .slice(0, 3)
            .map((f) => `${f.fornecedor} (${formatarReais(f.valor)})`)
            .join("; ")}
          .
        </p>
      )}
      <p className="pequeno discreto">
        Não inclui passagens aéreas emitidas pelo sistema da própria Câmara, que não são
        publicadas nos dados abertos.
      </p>
    </div>
  );
}

function MandatoDetalhe({
  atividade: a,
  fidelidade: f,
  posFid,
  sexo,
}: {
  atividade: Atividade | null;
  fidelidade: LinhaFidelidade[];
  posFid: ReturnType<typeof colocacao>;
  sexo: string | null;
}) {
  const fid = f.find((x) => x.periodo === "legislatura" && x.suficiente);
  const autor = sexo === "F" ? "autora" : "autor";
  return (
    <div className="leitura">
      <div className="secao-cab">
        <h2>Atividade legislativa</h2>
      </div>
      {a ? (
        <>
          <p>
            <span className="marca num">
              {a.apresentados} {a.apresentados === 1 ? "projeto" : "projetos"}
            </span>{" "}
            apresentados como {autor} principal nesta legislatura (PL, PLP, PEC e PDL).{" "}
            {a.aprovados_camara === 0
              ? "Nenhum foi aprovado na Câmara até agora."
              : `${a.aprovados_camara} ${a.aprovados_camara === 1 ? "foi aprovado" : "foram aprovados"} na Câmara${a.viraram_lei > 0 ? `, e ${a.viraram_lei} ${a.viraram_lei === 1 ? "virou lei" : "viraram lei"}` : ""}.`}
          </p>
          {a.aprovadas.length > 0 && (
            <ul className={estilos.aprovadas}>
              {a.aprovadas.slice(0, 5).map((x) => (
                <li key={x.proposicao}>
                  <a href={x.url}>{x.proposicao}</a>{" "}
                  <span className="discreto">
                    · {x.situacao === "Transformado em Norma Jurídica" ? "virou lei" : "aprovado na Câmara"}
                  </span>
                  {x.ementa && <span className={estilos.ementaCurta}>{ementaAtual(x.ementa)}</span>}
                </li>
              ))}
            </ul>
          )}
          <p className="pequeno discreto">
            Quantidade não é qualidade: um projeto aprovado pesa mais que dez parados.
          </p>
        </>
      ) : (
        <p className="discreto">Sem projetos apresentados como {autor} principal.</p>
      )}
      <div className="secao-cab" style={{ marginTop: 24 }}>
        <h2>Fidelidade ao partido</h2>
      </div>
      {fid && fid.taxa !== null ? (
        <p>
          Votou como a maioria da bancada em{" "}
          <span className="marca num">{formatarPct(fid.taxa)}</span> das {fid.n} votações
          comparáveis{posFid ? ` (${posFid.posicao}º mais fiel de ${posFid.total})` : ""}.
        </p>
      ) : (
        <p className="discreto">Votos insuficientes para calcular.</p>
      )}
    </div>
  );
}
