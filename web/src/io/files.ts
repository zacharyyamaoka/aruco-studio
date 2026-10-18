// Files in and out of the browser: a download from text or base64, a file
// picked from disk. No server: everything stays on this machine.

function download(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export function downloadText(name: string, text: string, type = "text/plain"): void {
  download(name, new Blob([text], { type }));
}

export function downloadBase64(name: string, b64: string, type: string): void {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  download(name, new Blob([bytes], { type }));
}

/** Ask for one file; resolves with its text, or null when none was picked. */
export function pickFile(accept: string): Promise<{ name: string; text: string } | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.style.display = "none";
    input.dataset.testid = "open-file";
    input.onchange = async () => {
      const f = input.files?.[0];
      input.remove();
      resolve(f ? { name: f.name, text: await f.text() } : null);
    };
    input.oncancel = () => { input.remove(); resolve(null); };
    document.body.appendChild(input);
    input.click();
  });
}

/** A file name from the document's name: "Forearm side" -> "forearm-side". */
export function slug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "aruco";
}
