// The Studio's one HostedFiles instance, made on first use and bound to
// useStudio. The UI (the title bar's document pill) imports this and nothing
// else of ./core's runtime.
// WHY once per page, outside React: the instance owns window listeners
// (Ctrl+S, focus, pagehide) and the session; StrictMode would make two in a
// component (simple-hosted-files web/src/notes.ts does the same).
import { HostedFiles } from "./core";
import { studioAdapter } from "./adapter";
import { HOSTED_APP, hostedServer } from "./config";
import { useStudio } from "../store";

let hosted: HostedFiles | null = null;

export function hostedFiles(): HostedFiles {
  if (hosted) return hosted;
  const adapter = studioAdapter(useStudio);
  // autosave is the SDK's default (on: existing, unlocked files only)
  hosted = new HostedFiles({ server: hostedServer(), app: HOSTED_APP, ...adapter.options });
  adapter.bind(hosted);
  return hosted;
}
