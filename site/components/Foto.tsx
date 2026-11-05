"use client";

// Foto oficial da Câmara; se não existir ou não carregar, mostra as iniciais.
import { useState } from "react";

import { iniciais } from "@/lib/escala";

import estilos from "./Foto.module.css";

export function Foto({
  url,
  nome,
  tamanho = 48,
}: {
  url: string | null;
  nome: string;
  tamanho?: number;
}) {
  const [falhou, setFalhou] = useState(!url);
  const estilo = { width: tamanho, height: tamanho, fontSize: Math.round(tamanho * 0.33) };
  if (falhou) {
    return (
      <span className={estilos.iniciais} style={estilo} aria-hidden="true">
        {iniciais(nome)}
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- foto oficial servida pela Câmara
    <img
      src={url!}
      alt=""
      width={tamanho}
      height={tamanho}
      loading="lazy"
      decoding="async"
      className={estilos.foto}
      style={estilo}
      onError={() => setFalhou(true)}
    />
  );
}
