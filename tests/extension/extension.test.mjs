// Tests for the browser extension's logic (run: node --test tests/extension/)
// Optional: FIXTURES=<dir with download.docx, slides.pptx, sheet.xlsx, pack.zip>

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";

import { buildFilename, siteFolder, typeFolder, splitName, datePrefix, withDatePrefix } from "../../browser_extension/lib/naming.js";
import { listZipEntries } from "../../browser_extension/lib/zip.js";
import { buildContext } from "../../browser_extension/lib/content.js";
import { askForTitle, cleanTitle } from "../../browser_extension/lib/openai.js";
import { blobOrigin, dataUrlToBytes, fetchBlobFromTabs } from "../../browser_extension/lib/blob.js";
import { fetchLocalFile } from "../../browser_extension/lib/localfile.js";

const FIX = process.env.FIXTURES;
const fixture = (n) => {
  const p = FIX && path.join(FIX, n);
  return p && existsSync(p) ? new Uint8Array(readFileSync(p)) : null;
};
const fetched = (bytes, contentType = "") => ({ bytes, contentType, truncated: false });

test("naming styles and safety", () => {
  assert.equal(buildFilename("Delfa Invoice 2026-0412 Office Supplies", "download (3).PDF"),
    "Delfa_Invoice_2026-0412_Office_Supplies.pdf");
  assert.equal(buildFilename("facture délfa", "a.pdf", { style: "Spaces" }), "Facture Délfa.pdf");
  assert.equal(buildFilename("Q3 Sales Report", "x.xlsx", { style: "snake_case" }), "q3_sales_report.xlsx");
  assert.equal(buildFilename("Q3 Sales Report", "x.tar.gz", { style: "kebab-case" }), "q3-sales-report.tar.gz");
  assert.equal(buildFilename('bad <name>: "x"/y?', "f.txt"), "Bad_Name_X_Y.txt");
  assert.equal(buildFilename("CON", "f.txt"), "CON_file.txt");
  const long = buildFilename("word ".repeat(40), "f.pdf", { maxLength: 40 });
  assert.ok(long.length <= 40 && long.endsWith(".pdf"));
  assert.deepEqual(splitName("archive.tar.gz"), ["archive", ".tar.gz"]);
});

test("YY-MM date prefix", () => {
  assert.equal(datePrefix(new Date(2026, 10, 7)), "26-11");
  assert.equal(datePrefix(new Date(2030, 0, 1)), "30-01");
  assert.equal(buildFilename("Bee Diagnostic Et Cadrage", "Bee-Diagnostic-et-cadrage-v1.pdf", { prefix: "26-11" }),
    "26-11 Bee_Diagnostic_Et_Cadrage.pdf");
  assert.equal(withDatePrefix("Github", "26-11"), "26-11 Github");
  assert.equal(withDatePrefix("26-11 Github", "26-11"), "26-11 Github");
  const long = buildFilename("word ".repeat(40), "f.pdf", { maxLength: 40, prefix: "26-11" });
  assert.ok(long.length <= 40 && long.startsWith("26-11 "), long);
});

test("folders", () => {
  assert.equal(siteFolder("https://www.github.com/x"), "Github");
  assert.equal(siteFolder("https://news.bbc.co.uk/x"), "Bbc");
  assert.equal(siteFolder("http://127.0.0.1/x"), null);
  assert.equal(typeFolder("a.PDF"), "Documents");
  assert.equal(typeFolder("a.tar.gz"), "Archives");
});

test("blob helpers", () => {
  assert.equal(blobOrigin("blob:https://www.canva.com/1234-abcd"), "https://www.canva.com");
  assert.equal(blobOrigin("blob:null/1234"), null);
  assert.equal(siteFolder("blob:https://www.canva.com/1234-abcd"), "Canva");
  const bytes = dataUrlToBytes("data:application/pdf;base64," + Buffer.from("%PDF-1.7 hi").toString("base64"));
  assert.equal(new TextDecoder().decode(bytes), "%PDF-1.7 hi");
});

test("blob PDF from a page is read through the tab", async () => {
  const pdf = "data:application/pdf;base64," + Buffer.from("%PDF-1.7 Bee Diagnostic").toString("base64");
  let injected;
  globalThis.chrome = {
    tabs: { query: async () => [
      { id: 1, url: "https://other.com/", active: false },
      { id: 7, url: "https://app.bee.ma/projects/42", active: true },
    ] },
    scripting: { executeScript: async (opts) => {
      injected = opts;
      return [{ frameId: 0, result: { dataUrl: pdf, size: 23, type: "application/pdf" } }];
    } },
  };
  const got = await fetchBlobFromTabs("blob:https://app.bee.ma/uuid-1", 25 * 1048576);
  assert.equal(injected.target.tabId, 7);
  assert.equal(injected.world, "MAIN");
  assert.equal(got.contentType, "application/pdf");
  const ctx = await buildContext({ filename: "Bee-Diagnostic-et-cadrage-v1.pdf", url: "blob:https://app.bee.ma/uuid-1" }, got);
  assert.equal(ctx.files.length, 1);
});

test("blob read failure gives a clear error", async () => {
  globalThis.chrome = {
    tabs: { query: async () => [{ id: 3, url: "https://app.bee.ma/", active: true }] },
    scripting: { executeScript: async () => [{ result: { error: "Failed to fetch" } }] },
  };
  await assert.rejects(fetchBlobFromTabs("blob:https://app.bee.ma/x", 1000), /Failed to fetch/);
});

test("local file:// PDF is read through the offscreen page", async () => {
  const pdf = "data:application/pdf;base64," + Buffer.from("%PDF-1.7 local").toString("base64");
  let msg;
  globalThis.chrome = {
    extension: { isAllowedFileSchemeAccess: async () => true },
    runtime: {
      getURL: (p) => "chrome-extension://id/" + p,
      getContexts: async () => [],
      sendMessage: async (m) => { msg = m; return { dataUrl: pdf, size: 14 }; },
    },
    offscreen: { createDocument: async () => {} },
  };
  const got = await fetchLocalFile("file:///C:/Users/me/Downloads/Bee.pdf", 1000);
  assert.equal(msg.target, "bee-offscreen");
  assert.equal(new TextDecoder().decode(got.bytes), "%PDF-1.7 local");
});

test("local file:// without permission explains how to allow it", async () => {
  globalThis.chrome = { extension: { isAllowedFileSchemeAccess: async () => false } };
  await assert.rejects(fetchLocalFile("file:///C:/x.pdf", 1000), /Allow access to file URLs/);
});

test("cleanTitle strips quotes and extension", () => {
  assert.equal(cleanTitle('"Delfa Invoice.pdf"'), "Delfa Invoice");
});

test("text content is read", async () => {
  const bytes = new TextEncoder().encode("INVOICE 2026-0412\nDelfa SARL");
  const ctx = await buildContext({ filename: "x.txt", url: "https://a.com/x.txt" }, fetched(bytes, "text/plain"));
  assert.match(ctx.text, /INVOICE 2026-0412/);
  assert.ok(ctx.readable);
});

test("pdf is attached as a file", async () => {
  const bytes = new TextEncoder().encode("%PDF-1.4 fake");
  const ctx = await buildContext({ filename: "doc.pdf", url: "https://a.com/doc.pdf" }, fetched(bytes, "application/pdf"));
  assert.equal(ctx.files.length, 1);
  assert.match(ctx.files[0].file_data, /^data:application\/pdf;base64,/);
});

for (const [file, expect] of [
  ["download.docx", /Facture N° 2026-0412[\s\S]*Delfa SARL/],
  ["slides.pptx", /Product Launch Roadmap 2027[\s\S]*Nova Phone/],
  ["sheet.xlsx", /Q3 Sales[\s\S]*Casablanca/],
  ["pack.zip", /my-lib\/README\.md/],
]) {
  test(`office/zip content: ${file}`, { skip: !fixture(file) && "no fixtures" }, async () => {
    const bytes = fixture(file);
    if (file.endsWith(".zip")) assert.ok(listZipEntries(bytes).length >= 2);
    const ctx = await buildContext({ filename: file, url: "https://a.com/" + file }, fetched(bytes));
    assert.match(ctx.text, expect);
  });
}

test("askForTitle sends schema + content and parses answer", async () => {
  let sent;
  globalThis.fetch = async (url, init) => {
    sent = JSON.parse(init.body);
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify({
      title: "Delfa Invoice 2026-0412", document_type: "Invoice", confidence: "high" }) } }] }), { status: 200 });
  };
  const r = await askForTitle({ apiKey: "sk-test", model: "gpt-5-mini",
    context: { text: "hello", images: ["data:image/jpeg;base64,AAA"], files: [] } });
  assert.equal(r.title, "Delfa Invoice 2026-0412");
  assert.equal(sent.reasoning_effort, "low");
  assert.equal(sent.response_format.type, "json_schema");
  assert.equal(sent.messages[1].content[1].type, "image_url");
});

test("askForTitle reports API errors", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { message: "Incorrect API key" } }), { status: 401 });
  await assert.rejects(
    askForTitle({ apiKey: "sk-bad", context: { text: "x", images: [], files: [] } }),
    /Incorrect API key/
  );
});
