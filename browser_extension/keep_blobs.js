// BeeOrganizer: runs in every page. Some sites delete a generated file's temporary
// blob: link right after starting the download, before BeeOrganizer can read it.
// We delay that cleanup by 2 minutes so the file can be read and named.
(() => {
  const original = URL.revokeObjectURL;
  if (!original || original.__beeOrganizer) return;
  const delayed = function (url) {
    setTimeout(() => original.call(URL, url), 120000);
  };
  delayed.__beeOrganizer = true;
  URL.revokeObjectURL = delayed;
})();
