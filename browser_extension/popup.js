const DEFAULTS = {
  enabled: true,
  model: "gpt-5-mini",
  style: "Title_Case",
  folderMode: "none",
  maxSizeMB: 25,
  maxLength: 80,
  notify: true,
  skipExtensions: "exe, msi, dmg, crx, torrent, iso",
};

const $ = (id) => document.getElementById(id);

const STATUS_LABEL = {
  RENAMED: "Renamed",
  UNCHANGED: "Kept name",
  SKIPPED: "Skipped",
  ERROR: "Error",
};

function setStatus(text, cls = "") {
  $("status").textContent = text;
  $("status").className = "status " + cls;
}

async function load() {
  const s = { ...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS)) };
  const { apiKey = "" } = await chrome.storage.local.get("apiKey");
  $("enabled").checked = s.enabled;
  $("apiKey").value = apiKey;
  $("model").value = s.model;
  $("style").value = s.style;
  $("folderMode").value = s.folderMode;
  $("maxSizeMB").value = s.maxSizeMB;
  $("skipExtensions").value = s.skipExtensions;
  $("notify").checked = s.notify;
  if (!apiKey) setStatus("Add your OpenAI key to start", "err");
}

function bind() {
  const sync = (key, value) => chrome.storage.sync.set({ [key]: value });
  $("enabled").onchange = (e) => sync("enabled", e.target.checked);
  $("notify").onchange = (e) => sync("notify", e.target.checked);
  $("model").onchange = (e) => sync("model", e.target.value.trim() || DEFAULTS.model);
  $("style").onchange = (e) => sync("style", e.target.value);
  $("folderMode").onchange = (e) => sync("folderMode", e.target.value);
  $("skipExtensions").onchange = (e) => sync("skipExtensions", e.target.value);
  $("maxSizeMB").onchange = (e) => {
    const v = Math.min(100, Math.max(1, parseInt(e.target.value, 10) || DEFAULTS.maxSizeMB));
    e.target.value = v;
    sync("maxSizeMB", v);
  };
  $("apiKey").onchange = async (e) => {
    const key = e.target.value.trim();
    await chrome.storage.local.set({ apiKey: key });
    await chrome.action.setBadgeText({ text: "" });
    setStatus(key ? "Key saved" : "Add your OpenAI key to start", key ? "ok" : "err");
  };
  $("testKey").onclick = async () => {
    const btn = $("testKey");
    btn.disabled = true;
    btn.textContent = "…";
    const key = $("apiKey").value.trim();
    await chrome.storage.local.set({ apiKey: key });
    const r = await chrome.runtime.sendMessage({ type: "testKey", apiKey: key, model: $("model").value.trim() });
    setStatus(r.message, r.ok ? "ok" : "err");
    btn.disabled = false;
    btn.textContent = "Test";
  };
  $("clear").onclick = async () => {
    await chrome.storage.local.set({ history: [] });
    render();
  };
}

function timeAgo(t) {
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(t).toLocaleDateString();
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function renderEntry(h) {
  const li = el("li");
  const names = el("div", "names");
  if (h.status === "RENAMED") {
    names.append(el("div", "old", h.originalName), el("div", "new", (h.folder ? h.folder + "/" : "") + h.newName));
  } else {
    names.append(el("div", "new", h.originalName));
  }
  const meta = el("div", "meta");
  const badge = el("span", `badge ${h.status}`, STATUS_LABEL[h.status] || h.status);
  meta.append(badge, el("span", "", timeAgo(h.time)));
  const show = el("button", "link", "Show");
  show.type = "button";
  show.onclick = () => chrome.downloads.show(h.downloadId);
  meta.append(show);
  li.append(names, meta);
  if (h.message) li.append(el("div", "why", h.message));
  return li;
}

async function render() {
  const { history = [] } = await chrome.storage.local.get("history");
  $("history").replaceChildren(...history.map(renderEntry));
  $("empty").hidden = history.length > 0;
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.history) render();
});

load();
bind();
render();
