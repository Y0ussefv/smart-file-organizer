// Reads a downloaded file's bytes and turns it into context the AI can read.

import { listZipEntries, readZipText } from "./zip.js";
import { splitName } from "./naming.js";

const MAX_TEXT = 12000;

const TEXT_EXTS = new Set([
  ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".xml", ".html", ".htm",
  ".yaml", ".yml", ".toml", ".ini", ".cfg", ".log", ".tex", ".srt", ".vtt", ".svg", ".rtf", ".eml", ".ics",
  ".py", ".js", ".mjs", ".jsx", ".ts", ".tsx", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cs",
  ".go", ".rs", ".rb", ".php", ".swift", ".dart", ".sql", ".sh", ".bat", ".ps1", ".lua", ".r",
  ".vue", ".css", ".scss", ".glsl", ".hlsl",
]);
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"]);
const ZIP_EXTS = new Set([".zip", ".jar", ".apk", ".whl", ".xpi", ".crx"]);

/** Download the file into memory (max `maxBytes`). Returns {bytes, contentType, truncated}. */
export async function fetchBytes(url, maxBytes, timeoutMs = 30000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { credentials: "include", signal: ctrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const contentType = (resp.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    const reader = resp.body.getReader();
    const chunks = [];
    let total = 0;
    let truncated = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      total += value.length;
      if (total >= maxBytes) {
        truncated = true;
        ctrl.abort();
        break;
      }
    }
    const bytes = new Uint8Array(Math.min(total, maxBytes));
    let off = 0;
    for (const c of chunks) {
      const take = Math.min(c.length, bytes.length - off);
      bytes.set(c.subarray(0, take), off);
      off += take;
      if (off >= bytes.length) break;
    }
    return { bytes, contentType, truncated };
  } finally {
    clearTimeout(timer);
  }
}

export function toBase64(bytes) {
  let bin = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
  }
  return btoa(bin);
}

function xmlText(xml) {
  return xml
    .replace(/<\/(w:p|a:p|text:p|p|row|si)>/g, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/[ \t]+/g, " ")
    .replace(/\n\s*\n+/g, "\n")
    .trim();
}

async function officeText(bytes, ext) {
  const entries = listZipEntries(bytes);
  const names = entries.map((e) => e.name);
  const parts = [];
  const core = await readZipText(bytes, entries, "docProps/core.xml");
  if (core) parts.push("Properties: " + xmlText(core));

  if (ext === ".docx") {
    parts.push(xmlText(await readZipText(bytes, entries, "word/document.xml")));
  } else if (ext === ".pptx") {
    const slides = names
      .filter((n) => /^ppt\/slides\/slide\d+\.xml$/.test(n))
      .sort((a, b) => parseInt(a.match(/\d+/)[0]) - parseInt(b.match(/\d+/)[0]))
      .slice(0, 15);
    for (const [i, s] of slides.entries()) {
      parts.push(`[Slide ${i + 1}] ` + xmlText(await readZipText(bytes, entries, s)));
    }
  } else if (ext === ".xlsx" || ext === ".xlsm") {
    const wb = await readZipText(bytes, entries, "xl/workbook.xml");
    const sheets = [...wb.matchAll(/<sheet [^>]*name="([^"]+)"/g)].map((m) => m[1]);
    if (sheets.length) parts.push("Sheets: " + sheets.join(", "));
    const shared = [...(await readZipText(bytes, entries, "xl/sharedStrings.xml")).matchAll(/<si>([\s\S]*?)<\/si>/g)]
      .map((m) => xmlText(m[1]));
    const sheetFiles = names
      .filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n))
      .sort((a, b) => parseInt(a.match(/\d+/)[0]) - parseInt(b.match(/\d+/)[0]))
      .slice(0, 3);
    for (const [i, sf] of sheetFiles.entries()) {
      const xml = await readZipText(bytes, entries, sf);
      const rows = [...xml.matchAll(/<row[^>]*>([\s\S]*?)<\/row>/g)].slice(0, 25).map((r) =>
        [...r[1].matchAll(/<c([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)]
          .map(([, attrs, inner = ""]) => {
            const t = (attrs.match(/\st="([^"]+)"/) || [])[1];
            if (t === "inlineStr") return xmlText(inner);
            const v = (inner.match(/<v>([\s\S]*?)<\/v>/) || [])[1] ?? "";
            return t === "s" ? shared[parseInt(v, 10)] ?? "" : v;
          })
          .filter(Boolean)
          .join(" | ")
      );
      parts.push(`[Sheet ${sheets[i] || i + 1}]\n` + rows.filter(Boolean).join("\n"));
    }
  } else if ([".odt", ".ods", ".odp"].includes(ext)) {
    parts.push(xmlText(await readZipText(bytes, entries, "content.xml")));
  } else if (ext === ".epub") {
    const opf = names.find((n) => n.endsWith(".opf"));
    if (opf) parts.push(xmlText(await readZipText(bytes, entries, opf)));
  }
  return parts.join("\n").slice(0, MAX_TEXT);
}

async function shrinkImage(bytes, mime) {
  // Resize big pictures to keep the request small (OffscreenCanvas works in service workers).
  try {
    const bmp = await createImageBitmap(new Blob([bytes], { type: mime }));
    const scale = Math.min(1, 1536 / Math.max(bmp.width, bmp.height));
    const canvas = new OffscreenCanvas(Math.round(bmp.width * scale), Math.round(bmp.height * scale));
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await canvas.convertToBlob({ type: "image/jpeg", quality: 0.88 });
    return "data:image/jpeg;base64," + toBase64(new Uint8Array(await blob.arrayBuffer()));
  } catch {
    return `data:${mime};base64,` + toBase64(bytes);
  }
}

function printableStrings(bytes) {
  const s = new TextDecoder("latin1").decode(bytes.subarray(0, 65536));
  return (s.match(/[\x20-\x7e]{6,}/g) || []).slice(0, 80).join("\n").slice(0, 3000);
}

/**
 * Build what the model will see.
 * Returns { text, images: [dataUrl], files: [{filename, file_data}], readable: bool }
 */
export async function buildContext({ filename, url, referrer, mime, size }, fetched) {
  const [, extRaw] = splitName(filename);
  const ext = extRaw.toLowerCase();
  const { bytes, contentType, truncated } = fetched;
  const type = mime || contentType || "";

  const header = [
    `Original filename: ${filename}`,
    `Extension: ${ext || "(none)"}`,
    `MIME type: ${type || "unknown"}`,
    `Size: ${size || bytes.length} bytes`,
    `Downloaded from: ${url}`,
  ];
  if (referrer) header.push(`Page: ${referrer}`);

  let body = "";
  const images = [];
  const files = [];

  try {
    if (ext === ".pdf" || type === "application/pdf") {
      if (!truncated) files.push({ filename: filename || "file.pdf", file_data: "data:application/pdf;base64," + toBase64(bytes) });
    } else if ([".docx", ".pptx", ".xlsx", ".xlsm", ".odt", ".ods", ".odp", ".epub"].includes(ext)) {
      if (!truncated) body = await officeText(bytes, ext);
    } else if (IMAGE_EXTS.has(ext) || (type.startsWith("image/") && type !== "image/svg+xml")) {
      if (!truncated) images.push(await shrinkImage(bytes, type || "image/jpeg"));
    } else if (ZIP_EXTS.has(ext) || type === "application/zip") {
      if (!truncated) {
        const entries = listZipEntries(bytes);
        body = `Archive with ${entries.length} entries:\n` + entries.slice(0, 80).map((e) => e.name).join("\n");
      }
    } else if (TEXT_EXTS.has(ext) || type.startsWith("text/") || /json|xml|javascript/.test(type)) {
      body = new TextDecoder("utf-8").decode(bytes.subarray(0, MAX_TEXT * 2)).slice(0, MAX_TEXT);
    } else {
      body = printableStrings(bytes);
      if (body) body = "Readable strings found in the binary:\n" + body;
    }
  } catch (e) {
    body = `[Could not read content: ${e.message}]`;
  }

  let text = header.join("\n");
  if (body.trim()) text += "\n\n--- FILE CONTENT ---\n" + body.trim();
  const readable = images.length > 0 || files.length > 0 || body.trim().length > 20;
  return { text, images, files, readable };
}
