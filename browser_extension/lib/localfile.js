// Reading "file:" downloads (a file from your own computer opened in Chrome, then saved again).
//
// Chrome only lets an extension read file:// URLs when the user turns on
// "Allow access to file URLs" in the extension's details page. Service workers can't
// load file:// themselves, so we use an offscreen document (an invisible extension page).

import { dataUrlToBytes } from "./blob.js";

export const FILE_ACCESS_HELP =
  'Turn on "Allow access to file URLs" for BeeOrganizer (chrome://extensions → BeeOrganizer → Details).';

async function ensureOffscreen() {
  const url = chrome.runtime.getURL("offscreen.html");
  if (chrome.runtime.getContexts) {
    const existing = await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"], documentUrls: [url] });
    if (existing.length) return;
  }
  try {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["BLOBS"],
      justification: "Read a local file that is being downloaded so it can be named from its content.",
    });
  } catch (e) {
    if (!/single offscreen|already/i.test(e.message || "")) throw e;
  }
}

/** Returns {bytes, contentType, truncated} or throws a readable Error. */
export async function fetchLocalFile(fileUrl, maxBytes) {
  const allowed = await chrome.extension.isAllowedFileSchemeAccess();
  if (!allowed) throw new Error(FILE_ACCESS_HELP);

  await ensureOffscreen();
  const r = await chrome.runtime.sendMessage({ target: "bee-offscreen", type: "readLocalFile", url: fileUrl, maxBytes });
  if (!r) throw new Error("Could not read the local file.");
  if (r.tooBig) {
    const err = new Error(`Larger than ${Math.round(maxBytes / 1048576)} MB.`);
    err.tooBig = true;
    throw err;
  }
  if (r.error) throw new Error(r.error);
  return { bytes: dataUrlToBytes(r.dataUrl), contentType: "", truncated: false };
}
