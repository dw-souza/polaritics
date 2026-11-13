import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { Foto } from "@/components/Foto";
import { Regua, type Marcador } from "@/components/Regua";
import { ReguaCamara } from "@/components/ReguaCamara";
import {
  VOTACOES,
  faixa,
  formatarDataCurta,
  formatarNota,
  formatarPct,
  fraseFaixa,
  lerVisao,
  type Votacoes,
} from "@/lib/escala";
import {
  URL_METODOLOGIA_MUNICIPAL,
  cargoVereador,
  filiacoes,
  mandatosDoVereador,
  municipio,
  notasDosPartidos,
  vereador,
  vereadoresDaLegislatura,
  votacoesQueMaisPesaram,
  type MandatoVereador,
  type Municipio,
  type PosicaoVereador,
  type Vereador,
} from "@/lib/municipal";

import estilos from "@/app/deputado/[id]/pagina.module.css";

type Props = PageProps<"/camaras/[municipio]/vereador/[id]">;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { municipio: slug, id } = await params;
  const [m, v] = await Promise.all([municipio(slug), vereador(slug, id)]);
  return { title: v && m ? `${v.nome} · ${m.nome}` : "Vereador" };
}

export default function PaginaVereador(props: Props) {
  return (
    <Suspense fallback={<p className="discreto">Carregando a ficha…</p>}>
      <Ficha {...props} />
    </Suspense>
  );
}

const ano = (d: string) => d.slice(0, 4);

async function Ficha({ params, searchParams }: Props) {
  const { municipio: slug, id } = await params;
  const { votacoes } = lerVisao(await searchParams);
  const [m, v] = await Promise.all([municipio(slug), vereador(slug, id)]);
  if (!m || !v) notFound();
  const [mandatos, fil, notas] = await Promise.all([
    mandatosDoVereador(slug, id),
    filiacoes(slug, id),
    notasDosPartidos(),
  ]);
  if (mandatos.length === 0) notFound();
  const atual = mandatos[0];
  const base = `/camaras/${slug}/vereador/${id}`;

  return (
    <article>
      <p className={estilos.migalha}>
        <Link href={`/camaras/${slug}`}>← Câmara de {m.nome}</Link>
      </p>
      <header className={estilos.identidade}>
        <Foto url={v.foto_url} nome={v.nome} tamanho={104} />
        <div>
          <h1>{v.nome}</h1>
          <p className={estilos.cargo}>
            {[cargoVereador(v.sexo), atual.partido, `${m.nome}-${m.uf}`].filter(Boolean).join(" · ")}
          </p>
        </div>
      </header>

      <div className="secao-cab" style={{ marginTop: 24 }}>
        <nav className="seg" aria-label="Votações consideradas">
          {(Object.keys(VOTACOES) as Votacoes[]).map((x) => (
            <Link
              key={x}
              href={x === "todas" ? base : `${base}?votacoes=${x}`}
              aria-current={x === votacoes ? "true" : undefined}
              scroll={false}
            >
              {VOTACOES[x].nome}
            </Link>
          ))}
        </nav>
        {mandatos.length > 1 && (
          <span className="pequeno discreto">
            {mandatos.length} legislaturas · a régua é recalibrada em cada uma
          </span>
        )}
      </div>

      {mandatos.map((mandato) => (
        <Legislatura
          key={mandato.legislatura}
          municipio={m}
          vereador={v}
          mandato={mandato}
          votacoes={votacoes}
          notas={notas}
        />
      ))}

      {fil.length > 0 && (
        <section className="secao">
          <div className="secao-cab">
            <h2>Filiações partidárias</h2>
            <span className="rotulo">Registradas na câmara</span>
          </div>
          <ul className="leitura pequeno">
            {fil.map((f) => (
              <li key={`${f.partido}-${f.inicio}`}>
                <strong>{f.partido}</strong> desde {formatarDataCurta(f.inicio)}
                {f.fim ? ` até ${formatarDataCurta(f.fim)}` : " (atual)"}
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}

async function Legislatura({
  municipio: m,
  vereador: v,
  mandato,
  votacoes,
  notas,
}: {
  municipio: Municipio;
  vereador: Vereador;
  mandato: MandatoVereador;
  votacoes: Votacoes;
  notas: Record<string, number>;
}) {
  const publicada = mandato.variantes.includes(votacoes);
  const [linhas, explicativas] = await Promise.all([
    vereadoresDaLegislatura(m.municipio, mandato.legislatura, votacoes),
    publicada
      ? votacoesQueMaisPesaram(m.municipio, v.id_vereador, mandato.legislatura, votacoes)
      : [],
  ]);
  const camara = linhas.flatMap((l) => (l.posicao ? [l.posicao] : []));
  const p = camara.find((x) => x.id_vereador === v.id_vereador);
  const colegas = p
    ? camara.filter((x) => x.grupo === p.grupo && x.id_vereador !== v.id_vereador)
    : [];
  const esp = mandato.partido ? (notas[mandato.partido] ?? null) : null;
  const ele = v.sexo === "F" ? "ela" : "ele";

  return (
    <section className="secao">
      <div className="secao-cab">
        <h2>
          {mandato.legislatura}ª legislatura · {ano(mandato.inicio)}–{ano(mandato.fim)}
        </h2>
        <span className="rotulo">
          {mandato.partido ? `${mandato.partido} nesta legislatura` : "sem partido registrado"}
        </span>
      </div>

      <Manchete p={p} colegas={colegas} mandato={mandato} />

      <div className={estilos.blocos} style={{ marginBottom: 24 }}>
        <div className={estilos.bloco}>
          <span className="rotulo">Posição pelos votos</span>
          {p ? (
            <>
              <span className={`${estilos.valor} num`}>
                {formatarNota(p.nota)} <small>{p.faixa_exibida.toLowerCase()}</small>
              </span>
              <span className={estilos.pos}>
                Entre {formatarNota(p.nota_p05)} e {formatarNota(p.nota_p95)}{" "}
                <span>(90% de certeza)</span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>{publicada ? "Votos insuficientes" : "Não publicada"}</span>
          )}
        </div>
        <div className={estilos.bloco}>
          <span className="rotulo">Na câmara</span>
          {p ? (
            <>
              <span className={`${estilos.valor} num`}>
                {p.posicao}º <small>de {p.n_vereadores}</small>
              </span>
              <span className={estilos.pos}>
                {p.posicao_p05 === p.posicao_p95
                  ? "da esquerda para a direita"
                  : `entre ${p.posicao_p05}º e ${p.posicao_p95}º`}{" "}
                <span>{p.posicao_p05 === p.posicao_p95 ? "" : "(90% de certeza)"}</span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>—</span>
          )}
          <details>
            <summary>O que é</summary>
            Ordem da esquerda (1º) para a direita entre os vereadores da legislatura, com a faixa
            de posições que os dados admitem.
          </details>
        </div>
        <div className={estilos.bloco}>
          <span className="rotulo">Com o prefeito</span>
          {mandato.gov_suficiente && mandato.gov_taxa !== null ? (
            <>
              <span className={`${estilos.valor} num`}>{formatarPct(mandato.gov_taxa)}</span>
              <span className={estilos.pos}>
                {mandato.gov_alinhados} de {mandato.gov_n_disputadas}{" "}
                <span>votações disputadas</span>
              </span>
            </>
          ) : mandato.gov_n_disputadas ? (
            <>
              <span className={`${estilos.valor} num`}>
                {mandato.gov_alinhados ?? 0} <small>de {mandato.gov_n_disputadas}</small>
              </span>
              <span className={estilos.pos}>
                <span>poucas votações para um percentual</span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Sem votações disputadas</span>
          )}
          <details>
            <summary>O que é</summary>
            Votos a favor dos projetos de autoria do prefeito
            {mandato.prefeito ? ` (${mandato.prefeito}, ${mandato.partido_prefeito})` : ""} nas
            votações em que alguém votou contra. Mede apoio ao prefeito, não ideologia.
          </details>
        </div>
        <div className={estilos.bloco}>
          <span className="rotulo">Presença</span>
          {mandato.pres_suficiente && mandato.pres_taxa !== null ? (
            <>
              <span className={`${estilos.valor} num`}>{formatarPct(mandato.pres_taxa)}</span>
              <span className={estilos.pos}>
                {mandato.pres_presentes} de {mandato.pres_sessoes} <span>sessões</span>
              </span>
            </>
          ) : (
            <span className={estilos.semDado}>Sessões insuficientes</span>
          )}
          <details>
            <summary>O que é</summary>
            Sessões ordinárias e extraordinárias com lista de presença registrada, durante o
            mandato.
          </details>
        </div>
      </div>

      {p ? (
        <div className={estilos.regua}>
          {p.fronteira && (
            <p className="aviso">
              <strong>Zona de fronteira.</strong> A nota fica muito perto do limite entre duas
              faixas: pequenas mudanças nas votações consideradas trocam o rótulo.
            </p>
          )}
          <Regua
            titulo={`Posição de ${v.nome} na escala de 0 a 10`}
            marcadores={marcadores(v.nome, p, mandato.partido, esp)}
          />
          <Comparacao nome={v.nome} p={p} partido={mandato.partido} esp={esp} />
          <details>
            <summary className="rotulo" style={{ cursor: "pointer" }}>
              Ver a câmara inteira nesta legislatura
            </summary>
            <div style={{ marginTop: 16 }}>
              <ReguaCamara
                posicoes={camara}
                hrefVereador={(id) => `/camaras/${m.municipio}/vereador/${id}`}
                destaque={v.id_vereador}
              />
            </div>
          </details>
          <p className="pequeno discreto">
            Baseado em {p.n_votos} votos nas {mandato.n_divergentes} votações com divergência ·{" "}
            {VOTACOES[votacoes].nome} · <a href={URL_METODOLOGIA_MUNICIPAL}>como é calculado</a>
          </p>
        </div>
      ) : (
        <p className="aviso">
          {publicada ? (
            <>
              <strong>Votos insuficientes.</strong> {v.nome} votou em menos de 10% das votações com
              divergência. Acontece com quem presidiu a câmara (o presidente quase não vota) e com
              suplentes que exerceram pouco tempo.
            </>
          ) : (
            <>
              <strong>Posição não publicada.</strong> Esta legislatura não passou nos critérios de
              validação nesta variante. Governismo e presença não dependem do modelo.
            </>
          )}
        </p>
      )}

      {explicativas.length > 0 && (
        <div style={{ marginTop: 28 }}>
          <div className="secao-cab">
            <h3>Votações que mais pesaram</h3>
            <span className="rotulo">As que mais levaram {ele} para o lado em que está</span>
          </div>
          <ol className={estilos.votos}>
            {explicativas.map((x) => (
              <li key={x.id_votacao}>
                <div>
                  <div className={estilos.pl}>
                    {x.url ? <a href={x.url}>{x.materia ?? "Votação"}</a> : (x.materia ?? "Votação")}
                  </div>
                  <div className={estilos.data}>
                    {formatarDataCurta(x.data)} ·{" "}
                    {x.tipo === "procedimento" ? "andamento da pauta" : "mérito"}
                  </div>
                </div>
                <div className="leitura">
                  {x.ementa && <p className={estilos.ementa}>{x.ementa}</p>}
                  <p className="pequeno">
                    Votou <span className={estilos.voto}>{x.voto}</span>
                    <span className="discreto"> · placar {x.placar}</span>
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function Manchete({
  p,
  colegas,
  mandato,
}: {
  p: PosicaoVereador | undefined;
  colegas: PosicaoVereador[];
  mandato: MandatoVereador;
}) {
  if (!p) return null;
  const f = fraseFaixa(p.faixa_exibida, p.fronteira);
  const nomes = colegas.map((c) => c.nome);
  const lista =
    nomes.length <= 3
      ? nomes.join(", ").replace(/, ([^,]*)$/, " e $1")
      : `${nomes.length} colegas`;
  return (
    <p className={estilos.manchete}>
      {f.antes} <span className="marca">{f.destaque}</span>
      {colegas.length === 0
        ? ", e nenhum colega vota de forma indistinguível nesta legislatura"
        : `, e vota de forma indistinguível de ${lista}`}
      {mandato.gov_suficiente && mandato.gov_taxa !== null && (
        <>
          . Acompanhou o prefeito em{" "}
          <span className="marca">{formatarPct(mandato.gov_taxa)}</span> das votações disputadas
          de projetos do Executivo
        </>
      )}
      .
    </p>
  );
}

function marcadores(
  nome: string,
  p: PosicaoVereador,
  partido: string | null,
  esp: number | null,
): Marcador[] {
  const m: Marcador[] = [
    { rotulo: nome, nota: p.nota, intervalo: [p.nota_p05, p.nota_p95], forma: "ponto" },
  ];
  if (partido && esp !== null) {
    m.push({
      rotulo: `${partido} segundo especialistas`,
      nota: esp,
      forma: "losango",
      detalhe: faixa(esp).toLowerCase(),
    });
  }
  return m;
}

function Comparacao({
  nome,
  p,
  partido,
  esp,
}: {
  nome: string;
  p: PosicaoVereador;
  partido: string | null;
  esp: number | null;
}) {
  if (!partido) return null;
  if (esp === null) {
    return (
      <p className="leitura">
        O {partido} não tem classificação de especialistas, então só a posição pelos votos é
        mostrada.
      </p>
    );
  }
  if (p.polo_unico) {
    return (
      <p className="leitura">
        Especialistas classificam o {partido} como <strong>{faixa(esp).toLowerCase()}</strong> (
        {formatarNota(esp)}). {nome} é o único vereador do seu lado da régua com partido
        classificado, por isso serve de referência para calibrá-la: a nota fica perto da do partido
        por construção, e a comparação não é informativa.
      </p>
    );
  }
  const lado =
    esp < p.nota_p05
      ? "mais à direita do que"
      : esp > p.nota_p95
        ? "mais à esquerda do que"
        : "em linha com";
  return (
    <p className="leitura">
      Especialistas classificam o {partido} como <strong>{faixa(esp).toLowerCase()}</strong> (
      {formatarNota(esp)}). Pelos votos, {nome} fica {lado} essa classificação.
    </p>
  );
}
