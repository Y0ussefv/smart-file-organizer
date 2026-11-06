// OpenAI call that turns file content into an exact title.

const API = "https://api.openai.com/v1";
export const DEFAULT_MODEL = "gpt-5-mini";

const SYSTEM_PROMPT = `You name files. You receive the real content of one file and must return an EXACT, specific title for its filename.

Rules:
- Use only facts present in the content: exact company / brand / product / person / project names, document type, invoice or reference numbers, dates, versions, places, topics.
- Be precise, not generic. Bad: "Invoice", "Report", "Image", "Document". Good: "Delfa Invoice 2026-0412 Office Supplies", "Ahmed Benali CV Data Analyst", "Q3 2026 Sales Report Morocco", "Golden Retriever Puppy On Beach".
- 3 to 10 words. No file extension.
- For images: describe exactly what is shown (readable text, logos, brand, scene, screenshot of which app/page).
- For code: what the program does and its main component name.
- Write the title in the main language of the content.
- Never invent facts. If the content is unreadable, use the metadata (page, site, original name) as precisely as possible and set confidence to "low".
Return JSON only.`;

const SCHEMA = {
  name: "file_title",
  strict: true,
  schema: {
    type: "object",
    additionalProperties: false,
    properties: {
      title: { type: "string" },
      document_type: { type: "string" },
      confidence: { type: "string", enum: ["high", "medium", "low"] },
    },
    required: ["title", "document_type", "confidence"],
  },
};

function isReasoningModel(model) {
  return /^(gpt-5|o1|o3|o4)/i.test(model || "");
}

export function cleanTitle(raw) {
  return (raw || "")
    .replace(/["'`*#]+/g, " ")
    .trim()
    .replace(/\.[A-Za-z0-9]{1,5}$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function post(apiKey, payload, timeoutMs) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(`${API}/chat/completions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
  } finally {
    clearTimeout(t);
  }
}

async function errorText(resp) {
  try {
    const j = await resp.json();
    return j?.error?.message || resp.statusText;
  } catch {
    return resp.statusText;
  }
}

/** Returns { title, documentType, confidence } or throws an Error with a readable message. */
export async function askForTitle({ apiKey, model = DEFAULT_MODEL, context, timeoutMs = 60000 }) {
  if (!apiKey) throw new Error("No OpenAI API key – add it in the extension popup.");
  const content = [{ type: "text", text: context.text }];
  for (const url of context.images.slice(0, 2)) {
    content.push({ type: "image_url", image_url: { url, detail: "high" } });
  }
  for (const f of context.files.slice(0, 1)) {
    content.push({ type: "file", file: f });
  }

  const payload = {
    model,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content },
    ],
    response_format: { type: "json_schema", json_schema: SCHEMA },
    max_completion_tokens: 2000,
  };
  if (isReasoningModel(model)) payload.reasoning_effort = "low";

  let resp = await post(apiKey, payload, timeoutMs);
  if (resp.status === 400 && payload.reasoning_effort) {
    const msg = await errorText(resp.clone());
    if (/reasoning/i.test(msg)) {
      delete payload.reasoning_effort;
      resp = await post(apiKey, payload, timeoutMs);
    }
  }
  if (!resp.ok) throw new Error(`OpenAI error ${resp.status}: ${await errorText(resp)}`);

  const json = await resp.json();
  const msg = json?.choices?.[0]?.message;
  if (!msg) throw new Error("OpenAI returned no answer.");
  if (msg.refusal) throw new Error("OpenAI refused: " + msg.refusal);
  const data = JSON.parse(msg.content || "{}");
  const title = cleanTitle(data.title);
  if (title.length < 2) throw new Error("OpenAI returned an empty title.");
  return { title, documentType: data.document_type || "", confidence: data.confidence || "" };
}

export async function testKey(apiKey, model = DEFAULT_MODEL) {
  if (!apiKey) return { ok: false, message: "Enter an API key first." };
  try {
    const r = await fetch(`${API}/models/${encodeURIComponent(model)}`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (r.ok) return { ok: true, message: `Key works – model "${model}" is available.` };
    if (r.status === 404) return { ok: false, message: `Key works, but model "${model}" is not available to your account.` };
    return { ok: false, message: `OpenAI error ${r.status}: ${await errorText(r)}` };
  } catch (e) {
    return { ok: false, message: "Network error: " + e.message };
  }
}
