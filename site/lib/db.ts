import { neon } from "@neondatabase/serverless";

// Conexão pooled do Neon (funções serverless abrem muitas conexões curtas).
const url = process.env.POLARITICS_DATABASE_URL_POOLED;
if (!url) {
  throw new Error("defina POLARITICS_DATABASE_URL_POOLED (em .env.local ou na Vercel)");
}

export const sql = neon(url);
