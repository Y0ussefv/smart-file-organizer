// BeeOrganizer – background service worker (standalone, no desktop app needed).
//
// When a download STARTS, Chrome asks extensions what the file should be called
// (downloads.onDeterminingFilename). We fetch the same file into memory, read its
// content, ask OpenAI for an exact title, and answer Chrome with the new name.
// Chrome then saves the file directly under that name.

import { buildFilename, siteFolder, typeFolder, splitName } from "./lib/naming.js";
import { fetchBytes, buildContext } from "./lib/content.js";
import { askForTitle, testKey, DEFAULT_MODEL } from "./lib/openai.js";

const HISTORY_LIMIT = 50;
const DECISION_TIMEOUT_MS = 90000;

export const DEFAULT_SETTINGS = {
  enabled: true,
  model: DEFAULT_MODEL,
  style: "Title_Case",        // Title_Case | snake_case | kebab-case | Spaces
  folderMode: "none",         // none | site | type
  maxSizeMB: 25,
  maxLength: 80,
  notify: true,
  skipExtensions: "exe, msi, dmg, crx, torrent, iso",
};

async function getSettings() {
  const sync = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  const { apiKey = "" } = await chrome.storage.local.get("apiKey"); // key never syncs to Google
  return { ...DEFAULT_SETTINGS, ...sync, apiKey: apiKey.trim() };
}

async function addHistory(entry) {
  const { history = [] } = await chrome.storage.local.get("history");
  history.unshift(entry);
  await chrome.storage.local.set({ history: history.slice(0, HISTORY_LIMIT) });
}

let busy = 0;
async function setBusy(delta) {
  busy = Math.max(0, busy + delta);
  await chrome.action.setBadgeBackgroundColor({ color: "#4f6bed" });
  await chrome.action.setBadgeText({ text: busy ? String(busy) : "" });
}

function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error("Took too long – kept original name.")), ms)),
  ]);
}

/** Decide the new name for a download. Returns {suggestion, entry}. */
async function decideName(item, settings) {
  const originalName = (item.filename || "").split(/[\\/]/).pop() || "download";
  const url = item.finalUrl || item.url;
  const entry = {
    id: `dl-${item.id}-${Date.now()}`,
    downloadId: item.id,
    time: Date.now(),
    url,
    originalName,
    newName: originalName,
    status: "UNCHANGED",
    message: "",
  };

  const [, ext] = splitName(originalName);
  const skip = settings.skipExtensions.split(",").map((s) => s.trim().replace(/^\./, "").toLowerCase()).filter(Boolean);
  if (ext && skip.includes(ext.slice(1).toLowerCase())) {
    return { entry: { ...entry, status: "SKIPPED", message: `.${ext.slice(1)} files are skipped (see settings).` } };
  }
  if (!/^(https?|data):/i.test(url)) {
    return { entry: { ...entry, status: "SKIPPED", message: "This download type cannot be read by the extension." } };
  }
  const maxBytes = settings.maxSizeMB * 1024 * 1024;
  if (item.fileSize > maxBytes || item.totalBytes > maxBytes) {
    return { entry: { ...entry, status: "SKIPPED", message: `Larger than ${settings.maxSizeMB} MB.` } };
  }

  const fetched = await fetchBytes(url, maxBytes);
  if (fetched.truncated && !/^text\//.test(fetched.contentType)) {
    return { entry: { ...entry, status: "SKIPPED", message: `Larger than ${settings.maxSizeMB} MB.` } };
  }
  const context = await buildContext(
    { filename: originalName, url, referrer: item.referrer, mime: item.mime, size: item.fileSize || item.totalBytes },
    fetched
  );

  const ai = await askForTitle({ apiKey: settings.apiKey, model: settings.model, context });
  const newName = buildFilename(ai.title, originalName, { style: settings.style, maxLength: settings.maxLength });
  if (!newName) return { entry: { ...entry, message: "AI title was empty." } };

  let folder = null;
  if (settings.folderMode === "site") folder = siteFolder(item.referrer || url);
  if (settings.folderMode === "type") folder = typeFolder(newName);

  const path = folder ? `${folder}/${newName}` : newName;
  return {
    suggestion: { filename: path, conflictAction: "uniquify" },
    entry: {
      ...entry,
      newName,
      folder,
      status: "RENAMED",
      documentType: ai.documentType,
      confidence: ai.confidence,
      message: `${ai.documentType || "File"} · confidence ${ai.confidence || "?"}`,
    },
  };
}

async function handleDownload(item) {
  const settings = await getSettings();
  if (!settings.enabled || item.byExtensionId === chrome.runtime.id) return null;
  if (!settings.apiKey) {
    await chrome.action.setBadgeBackgroundColor({ color: "#d93025" });
    await chrome.action.setBadgeText({ text: "key" });
    return null;
  }

  await setBusy(+1);
  let result;
  try {
    result = await withTimeout(decideName(item, settings), DECISION_TIMEOUT_MS);
  } catch (e) {
    result = {
      entry: {
        id: `dl-${item.id}-${Date.now()}`,
        downloadId: item.id,
        time: Date.now(),
        url: item.finalUrl || item.url,
        originalName: (item.filename || "").split(/[\\/]/).pop(),
        newName: (item.filename || "").split(/[\\/]/).pop(),
        status: "ERROR",
        message: e.message || String(e),
      },
    };
  } finally {
    await setBusy(-1);
  }

  await addHistory(result.entry);
  if (settings.notify && result.entry.status === "RENAMED") {
    const shown = result.entry.folder ? `${result.entry.folder}/${result.entry.newName}` : result.entry.newName;
    chrome.notifications.create(result.entry.id, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "Saved with a smart name",
      message: `${result.entry.originalName}\n→ ${shown}`,
      buttons: [{ title: "Show in folder" }],
    });
  } else if (settings.notify && result.entry.status === "ERROR") {
    chrome.notifications.create(result.entry.id, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "Kept the original name",
      message: `${result.entry.originalName}: ${result.entry.message}`.slice(0, 250),
    });
  }
  return result.suggestion || null;
}

// ---- Events (registered at top level so Chrome wakes the worker) ---------

chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  handleDownload(item)
    .then((s) => (s ? suggest(s) : suggest()))
    .catch(() => suggest());
  return true; // we will call suggest() asynchronously
});

chrome.notifications.onButtonClicked.addListener(async (notifId) => {
  const { history = [] } = await chrome.storage.local.get("history");
  const entry = history.find((h) => h.id === notifId);
  if (entry) chrome.downloads.show(entry.downloadId);
  chrome.notifications.clear(notifId);
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg?.type === "testKey") {
      const s = await getSettings();
      return testKey(msg.apiKey ?? s.apiKey, msg.model || s.model);
    }
    return { ok: false, message: "Unknown request" };
  })().then(sendResponse);
  return true;
});

chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  const current = await chrome.storage.sync.get(null);
  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...current });
  if (reason === "install") chrome.action.openPopup?.().catch(() => {});
});
