// Invisible BeeOrganizer page: reads local file:// files for the background worker
// (only works when "Allow access to file URLs" is on for the extension).

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.target !== "bee-offscreen" || msg.type !== "readLocalFile") return false;

  const xhr = new XMLHttpRequest();
  xhr.open("GET", msg.url);
  xhr.responseType = "blob";
  xhr.onload = () => {
    const blob = xhr.response;
    // file:// requests report status 0 on success
    if (!blob || (xhr.status !== 0 && xhr.status !== 200)) {
      sendResponse({ error: "Could not read the local file." });
      return;
    }
    if (blob.size > msg.maxBytes) {
      sendResponse({ tooBig: true, size: blob.size });
      return;
    }
    const fr = new FileReader();
    fr.onload = () => sendResponse({ dataUrl: fr.result, size: blob.size });
    fr.onerror = () => sendResponse({ error: "Could not read the local file." });
    fr.readAsDataURL(blob);
  };
  xhr.onerror = () => sendResponse({ error: "Could not read the local file (is file access allowed?)." });
  xhr.send();
  return true; // async response
});
