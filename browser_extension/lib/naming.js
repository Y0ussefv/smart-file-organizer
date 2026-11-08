// Filename building: sanitizing, naming styles, folders.

const COMPOUND_EXTS = [".tar.gz", ".tar.bz2", ".tar.xz", ".d.ts", ".spec.ts", ".user.js"];
const WINDOWS_RESERVED = new Set([
  "con", "prn", "aux", "nul",
  "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
  "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
]);

export function splitName(name) {
  const base = (name || "").split(/[\\/]/).pop();
  const lower = base.toLowerCase();
  for (const ext of COMPOUND_EXTS) {
    if (lower.endsWith(ext) && lower.length > ext.length) {
      return [base.slice(0, -ext.length), base.slice(-ext.length)];
    }
  }
  const dot = base.lastIndexOf(".");
  if (dot <= 0 || base.length - dot > 10) return [base, ""];
  return [base.slice(0, dot), base.slice(dot)];
}

function words(title) {
  return (title || "")
    .normalize("NFC")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, " ")
    .replace(/[\[\](){}'`,;!#$%^&+=~@]/g, " ")
    .split(/[\s_]+/)
    .map((w) => w.replace(/^[.\-]+|[.\-]+$/g, ""))
    .filter(Boolean);
}

function capitalize(w) {
  return w.charAt(0).toLocaleUpperCase() + w.slice(1);
}

export function applyStyle(title, style) {
  const ws = words(title);
  switch (style) {
    case "snake_case":
      return ws.map((w) => w.toLocaleLowerCase()).join("_");
    case "kebab-case":
      return ws.map((w) => w.toLocaleLowerCase()).join("-");
    case "Spaces":
      return ws.map(capitalize).join(" ");
    case "Title_Case":
    default:
      return ws.map(capitalize).join("_");
  }
}

function truncateStem(stem, max) {
  if (stem.length <= max) return stem;
  const cut = stem.slice(0, max);
  const lastSep = Math.max(cut.lastIndexOf("_"), cut.lastIndexOf("-"), cut.lastIndexOf(" "));
  return (lastSep > max * 0.5 ? cut.slice(0, lastSep) : cut).replace(/[_\-\s.]+$/, "");
}

/** Title + original filename -> safe new filename (keeps the original extension). */
/** "26-11" for November 2026 (last two digits of the year, then the month). */
export function datePrefix(date = new Date()) {
  const yy = String(date.getFullYear() % 100).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  return `${yy}-${mm}`;
}

/** Prepends "YY-MM " unless the name already starts with it. */
export function withDatePrefix(name, prefix) {
  if (!prefix || !name) return name;
  return name.startsWith(prefix + " ") ? name : `${prefix} ${name}`;
}

export function buildFilename(title, originalName, { style = "Title_Case", maxLength = 80, prefix = "" } = {}) {
  const [, ext] = splitName(originalName);
  let stem = applyStyle(title, style);
  if (!stem) return null;
  const prefixLen = prefix ? prefix.length + 1 : 0;
  stem = truncateStem(stem, Math.max(10, maxLength - ext.length - prefixLen));
  stem = stem.replace(/[.\s]+$/, "");
  if (WINDOWS_RESERVED.has(stem.toLowerCase())) stem += "_file";
  return withDatePrefix(stem, prefix) + ext.toLowerCase();
}

export function siteFolder(url) {
  let host = "";
  try {
    host = new URL((url || "").replace(/^blob:/i, "")).hostname.toLowerCase();
  } catch {
    return null;
  }
  if (!host || host === "localhost" || /^[\d.]+$/.test(host) || host.includes(":")) return null;
  const parts = host.split(".").filter((p) => p && !["www", "m", "dl", "download", "downloads", "cdn"].includes(p));
  if (!parts.length) return null;
  let name = parts[0];
  if (parts.length >= 3 && ["co", "com", "net", "org", "gov", "ac", "edu"].includes(parts[parts.length - 2])) {
    name = parts[parts.length - 3];
  } else if (parts.length >= 2) {
    name = parts[parts.length - 2];
  }
  name = name.replace(/[^a-z0-9\-_]/g, "");
  return name ? capitalize(name) : null;
}

const TYPE_FOLDERS = {
  Documents: [".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex", ".epub"],
  Spreadsheets: [".xls", ".xlsx", ".csv", ".tsv", ".ods"],
  Presentations: [".ppt", ".pptx", ".odp", ".key"],
  Images: [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg", ".heic", ".ico", ".avif"],
  Videos: [".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv"],
  Audio: [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
  Archives: [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".tar.gz", ".tar.bz2"],
  Installers: [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage", ".apk"],
  Code: [".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".go", ".rs", ".json", ".xml", ".html", ".sql"],
  Fonts: [".ttf", ".otf", ".woff", ".woff2"],
};

export function typeFolder(filename) {
  const [, ext] = splitName(filename);
  const e = ext.toLowerCase();
  for (const [folder, exts] of Object.entries(TYPE_FOLDERS)) {
    if (exts.includes(e)) return folder;
  }
  return e ? "Other" : null;
}
