// Verify accuracy (CoreApi.verify / readable): the simulated camera bench.
// A stub mounted by App so lanes can build it without touching App.tsx;
// lane "verify-ui" of the 2026-10-18 V1 build replaces its body.
import { useStudio } from "../store";

export function VerifyDialog() {
  const open = useStudio((s) => s.modal === "verify");
  if (!open) return null;
  return null;
}
