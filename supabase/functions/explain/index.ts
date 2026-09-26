// DiaCausal "explain" Edge Function: rewrites retrieved evidence in plain words with Google's Gemini
// (free tier), citing only the passages. Research prototype for clinician evaluation; not a marketed
// medical device; not for unsupervised clinical use.
//
// Security:
// - Only a signed-in person with an APPROVED account and a verified authenticator (aal2) may call it.
// - The browser sends only the question and the IDs of the passages it found. The passages are rebuilt
//   HERE from the published evidence index, so the function cannot be used as a general chatbot and
//   patient values are never sent (the Try it screen never calls it).
// - The Gemini key is a Supabase secret (GEMINI_API_KEY), never in the repo or the browser.
// - Nothing about the question is logged. The browser runs the citation checker (web/explain.js) on
//   the answer and falls back to quoted sentences if any sentence fails.
//
// The prompt below must stay identical to diacausal_rag/prompt.v1.txt (a test compares them).
import { createClient } from "npm:@supabase/supabase-js@2";

const PROMPT = `You write short explanations for a clinical decision-support research prototype.
Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Rules:
1. Use ONLY the numbered passages below. Do not add any fact that is not in them.
2. Every sentence must end with the number of the passage it comes from, in square brackets, like [1] or [2][3].
3. Never mention a drug dose, strength or number of tablets.
4. Write at most {max_sentences} short sentences in plain English for a doctor.
5. If the passages do not answer the question, reply with exactly: INSUFFICIENT_EVIDENCE

Question: {question}

Passages:
{passages}
`;
const EVIDENCE_URL = Deno.env.get("EVIDENCE_URL") ?? "https://diacausal.netlify.app/evidence.json";
const MODEL = Deno.env.get("GEMINI_MODEL") ?? "gemini-flash-latest";
const ORIGINS = (Deno.env.get("ALLOWED_ORIGINS") ?? "https://diacausal.netlify.app").split(",");
const MAX_QUESTION = 300;
const MAX_PASSAGES = 5;

type Chunk = { chunk_id: string; text: string; withheld: boolean; citation: { source_id: string; section: string } };
type Index = { chunks: Chunk[]; config: { explain_max_sentences: number }; dose_question_pattern: string };
let cache: { at: number; index: Index } | null = null;

async function evidence(): Promise<Index> {
  if (!cache || Date.now() - cache.at > 10 * 60 * 1000) {
    const r = await fetch(EVIDENCE_URL);
    if (!r.ok) throw new Error("evidence index unavailable");
    cache = { at: Date.now(), index: await r.json() };
  }
  return cache.index;
}

function cors(req: Request): Record<string, string> {
  const origin = req.headers.get("Origin") ?? "";
  return {
    "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

function reply(req: Request, status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify({ ...body, intended_use:
    "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use." }),
    { status, headers: { ...cors(req), "Content-Type": "application/json" } });
}

function claims(jwt: string): Record<string, unknown> {
  try { return JSON.parse(atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); } catch { return {}; }
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
  if (req.method !== "POST") return reply(req, 405, { error: "method_not_allowed" });

  const jwt = (req.headers.get("Authorization") ?? "").replace(/^Bearer /, "");
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: `Bearer ${jwt}` } },
  });
  const { data: user } = await supabase.auth.getUser(jwt);
  if (!user?.user) return reply(req, 401, { error: "sign_in_required" });
  if (claims(jwt).aal !== "aal2") return reply(req, 403, { error: "authenticator_code_required" });
  const { data: profile } = await supabase.from("profiles").select("approved,rejected").eq("id", user.user.id).single();
  if (!profile?.approved || profile.rejected) return reply(req, 403, { error: "account_not_approved" });

  let body: { question?: unknown; chunk_ids?: unknown };
  try { body = await req.json(); } catch { return reply(req, 422, { error: "invalid_json" }); }
  const question = typeof body.question === "string" ? body.question.trim() : "";
  const ids = Array.isArray(body.chunk_ids) ? body.chunk_ids.filter((x) => typeof x === "string") as string[] : [];
  if (!question || question.length > MAX_QUESTION || !ids.length || ids.length > MAX_PASSAGES) {
    return reply(req, 422, { error: "question (1-300 characters) and 1-5 chunk_ids are required" });
  }

  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) return reply(req, 503, { error: "not_configured" });

  let index: Index;
  try { index = await evidence(); } catch { return reply(req, 502, { error: "evidence_unavailable" }); }
  if (new RegExp(index.dose_question_pattern, "i").test(question)) return reply(req, 422, { error: "no_doses" });
  const byId = new Map(index.chunks.map((c) => [c.chunk_id, c]));
  const numbered: string[] = [];
  ids.forEach((id, i) => {
    const c = byId.get(id);
    if (c && !c.withheld) numbered.push(`[${i + 1}] (${c.citation.source_id}, ${c.citation.section}) ${c.text}`);
  });
  if (!numbered.length) return reply(req, 422, { error: "no_usable_passages" });

  const prompt = PROMPT.replace("{max_sentences}", () => String(index.config.explain_max_sentences))
    .replace("{question}", () => question.replace(/[{}]/g, "")).replace("{passages}", () => numbered.join("\n\n"));
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": key },
    body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }], generationConfig: { temperature: 0 } }),
  });
  if (!r.ok) return reply(req, 502, { error: r.status === 429 ? "free_quota_used_up" : "model_unavailable" });
  const out = await r.json();
  const text = out?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? "").join("") ?? "";
  return reply(req, 200, { text, model: MODEL });
});
