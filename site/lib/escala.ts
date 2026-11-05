// Faixas fixas da escala 0–10 (docs/metodologia.md, seção 4.3) e visões selecionáveis (4.2.1).

export const FAIXAS = [
  { limite: 1.5, rotulo: "Mais à esquerda" },
  { limite: 3.0, rotulo: "Esquerda" },
  { limite: 4.49, rotulo: "Centro-esquerda" },
  { limite: 5.5, rotulo: "Centro" },
  { limite: 7.0, rotulo: "Centro-direita" },
  { limite: 8.5, rotulo: "Direita" },
  { limite: 10.0, rotulo: "Mais à direita" },
] as const;

export function faixa(nota: number): string {
  const n = Math.round(Math.min(Math.max(nota, 0), 10) * 100) / 100;
  return (FAIXAS.find((f) => n <= f.limite) ?? FAIXAS[6]).rotulo;
}

// Início e fim de cada faixa na escala, para desenhar a régua.
export const INTERVALOS_FAIXAS = FAIXAS.map((f, i) => ({
  rotulo: f.rotulo,
  inicio: i === 0 ? 0 : FAIXAS[i - 1].limite,
  fim: f.limite,
  indice: i + 1,
}));

export type Regua = "voto" | "campo";
export type Votacoes = "todas" | "merito";

export const VISAO_PADRAO = { regua: "voto", votacoes: "todas" } as const;

export const REGUAS: Record<Regua, { nome: string; pergunta: string }> = {
  voto: {
    nome: "Comportamento de voto",
    pergunta:
      "Pelo jeito que vota, onde este parlamentar está? Isso bate com o que o partido diz ser?",
  },
  campo: {
    nome: "Dentro do campo do partido",
    pergunta: "Comparado ao próprio partido, este parlamentar é mais moderado ou mais radical?",
  },
};

export const VOTACOES: Record<Votacoes, { nome: string; explicacao: string }> = {
  todas: {
    nome: "Todas as votações",
    explicacao:
      "Inclui as votações de andamento da pauta (urgência, adiamento, retirada), em que o apoio ou a oposição ao governo pesa mais.",
  },
  merito: {
    nome: "Só mérito",
    explicacao: "Considera apenas as votações sobre o conteúdo dos projetos.",
  },
};

export function lerVisao(params: Record<string, string | string[] | undefined>) {
  const regua: Regua = params.regua === "campo" ? "campo" : "voto";
  const votacoes: Votacoes = params.votacoes === "merito" ? "merito" : "todas";
  return { regua, votacoes };
}

export function hrefVisao(base: string, regua: Regua, votacoes: Votacoes): string {
  const q = new URLSearchParams();
  if (regua !== VISAO_PADRAO.regua) q.set("regua", regua);
  if (votacoes !== VISAO_PADRAO.votacoes) q.set("votacoes", votacoes);
  const s = q.toString();
  return s ? `${base}?${s}` : base;
}

const fmtNota = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmtPct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 0 });
const fmtPctDecimal = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const fmtData = new Intl.DateTimeFormat("pt-BR", { dateStyle: "long", timeZone: "UTC" });
const fmtDataCurta = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeZone: "UTC" });

export const formatarNota = (n: number) => fmtNota.format(n);
export const formatarPct = (n: number) => fmtPct.format(n);
// Rankings: uma casa decimal, para valores próximos (99,6% e 99,8%) não parecerem empate.
export const formatarPctDecimal = (n: number) => fmtPctDecimal.format(n);

// Ementas reformuladas trazem o texto original seguido de "NOVA EMENTA:"; fica só a atual.
export const ementaAtual = (ementa: string) => {
  const i = ementa.toUpperCase().lastIndexOf("NOVA EMENTA:");
  return (i >= 0 ? ementa.slice(i + "NOVA EMENTA:".length) : ementa).trim();
};
export const formatarData = (d: string | Date) => fmtData.format(new Date(d));
export const formatarDataCurta = (d: string | Date) => fmtDataCurta.format(new Date(d));

// Posição em % da largura da régua.
export const pos = (nota: number) => `${(Math.min(Math.max(nota, 0), 10) / 10) * 100}%`;

// Índice 1–7 da faixa, para a cor (--faixa-N).
export const indiceFaixa = (nota: number) => FAIXAS.findIndex((f) => f.rotulo === faixa(nota)) + 1;

// Frase da manchete por faixa ("Vota no centro", "Vota mais à direita").
const VERBO_FAIXA: Record<string, string> = {
  "Mais à esquerda": "Vota mais à esquerda",
  Esquerda: "Vota na esquerda",
  "Centro-esquerda": "Vota na centro-esquerda",
  Centro: "Vota no centro",
  "Centro-direita": "Vota na centro-direita",
  Direita: "Vota na direita",
  "Mais à direita": "Vota mais à direita",
};

export function fraseFaixa(faixaExibida: string, fronteira: boolean): { antes: string; destaque: string } {
  if (fronteira) {
    return { antes: "Vota na fronteira entre", destaque: faixaExibida.replace(/^Entre /, "") };
  }
  const verbo = VERBO_FAIXA[faixaExibida] ?? "Vota em";
  // separa o verbo do nome da faixa, para o marca-texto cair só no nome
  const corte = verbo.lastIndexOf(" ");
  return verbo.startsWith("Vota mais")
    ? { antes: "Vota", destaque: verbo.slice(5) }
    : { antes: verbo.slice(0, corte), destaque: verbo.slice(corte + 1) };
}

const NOMES_CURTOS: Record<string, string> = {
  "Luiz Inácio Lula da Silva": "Lula",
  "Jair Bolsonaro": "Bolsonaro",
};
export const nomeCurtoGoverno = (chefe: string) => NOMES_CURTOS[chefe] ?? chefe;

export const cargo = (sexo: string | null) =>
  sexo === "F" ? "Deputada federal" : sexo === "M" ? "Deputado federal" : "Deputado(a) federal";

export const iniciais = (nome: string) =>
  nome
    .split(" ")
    .filter((p) => p.length > 2)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();

export const UFS: Record<string, string> = {
  AC: "Acre", AL: "Alagoas", AM: "Amazonas", AP: "Amapá", BA: "Bahia", CE: "Ceará",
  DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MG: "Minas Gerais",
  MS: "Mato Grosso do Sul", MT: "Mato Grosso", PA: "Pará", PB: "Paraíba", PE: "Pernambuco",
  PI: "Piauí", PR: "Paraná", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RO: "Rondônia",
  RR: "Roraima", RS: "Rio Grande do Sul", SC: "Santa Catarina", SE: "Sergipe", SP: "São Paulo",
  TO: "Tocantins",
};
