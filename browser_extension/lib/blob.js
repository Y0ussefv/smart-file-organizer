// Reading "blob:" downloads.
//
// Web apps (Canva, Notion, online PDF editors, "Export as PDF" buttons…) build the
// file inside the page and hand Chrome a temporary blob: URL. Only that page can read
// it, so we run a tiny reader inside the page's tab(s) and get the bytes back.

/** "data:application/pdf;base64,AAAA" -> Uint8Array */
export function dataUrlToBytes(dataUrl) {
  const comma = dataUrl.indexOf(",");
  const meta = dataUrl.slice(5, comma);
  const payload = dataUrl.slice(comma + 1);
  if (/;base64/i.test(meta)) {
    const bin = atob(payload);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  return new TextEncoder().encode(decodeURIComponent(payload));
}

/** The origin a blob: URL belongs to ("blob:https://a.com/uuid" -> "https://a.com"), or null. */
export function blobOrigin(blobUrl) {
  try {
    const o = new URL(blobUrl.replace(/^blob:/i, "")).origin;
    return o && o !== "null" ? o : null;
  } catch {
    return null;
  }
}

// Runs INSIDE the web page (MAIN world). Must be self-contained.
function readBlobInPage(url, maxBytes) {
  return fetch(url)
    .then((r) => r.blob())
    .then((b) => {
      if (b.size > maxBytes) return { tooBig: true, size: b.size, type: b.type };
      return new Promise((resolve) => {
        const fr = new FileReader();
        fr.onload = () => resolve({ dataUrl: fr.result, size: b.size, type: b.type });
        fr.onerror = () => resolve({ error: "read failed" });
        fr.readAsDataURL(b);
      });
    })
    .catch((e) => ({ error: String(e && e.message ? e.message : e) }));
}

/**
 * Returns {bytes, contentType, truncated} like fetchBytes(), or throws a readable Error.
 */
export async function fetchBlobFromTabs(blobUrl, maxBytes) {
  const origin = blobOrigin(blobUrl);
  const all = await chrome.tabs.query({});
  // Tabs of the same site first, then the active tabs (blob may come from an iframe).
  const sameSite = origin ? all.filter((t) => t.url && t.url.startsWith(origin)) : [];
  const active = all.filter((t) => t.active && !sameSite.includes(t));
  const candidates = [...sameSite, ...active].filter((t) => t.id != null && /^https?:/i.test(t.url || ""));

  let lastError = "the page that created this file was closed";
  for (const tab of candidates) {
    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        world: "MAIN",
        func: readBlobInPage,
        args: [blobUrl, maxBytes],
      });
    } catch (e) {
      lastError = e.message || String(e);
      continue;
    }
    for (const r of results || []) {
      const v = r && r.result;
      if (!v) continue;
      if (v.tooBig) {
        const err = new Error(`Larger than ${Math.round(maxBytes / 1048576)} MB.`);
        err.tooBig = true;
        throw err;
      }
      if (v.dataUrl) {
        return { bytes: dataUrlToBytes(v.dataUrl), contentType: (v.type || "").toLowerCase(), truncated: false };
      }
      if (v.error) lastError = v.error;
    }
  }
  throw new Error(`Could not read this page-generated file (${lastError}).`);
}
