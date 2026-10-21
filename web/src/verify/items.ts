// The markers Verify looks at (./VerifyDialog.tsx's bench and ./RangeView.tsx's
// strip): one per feature that plans, with its request and its last plan.
import type { MarkerPlan, PlanRequest } from "../core/contract";
import { idRange, planRequest, type Doc, type Feature } from "../model/doc";

export interface Item { f: Feature; req: PlanRequest; plan: MarkerPlan | undefined; key: string; slot: number }

/** "Marker #39", "Grid 2×3 #0–5", "ChArUco 5×4 #10–19". */
export function markerName(f: Feature, plan?: MarkerPlan): string {
  const m = f.marker, ids = idRange(m, plan?.ids);
  if (m.type === "single") return `Marker ${ids}`;
  return `${m.type === "grid" ? "Grid" : "ChArUco"} ${plan?.cols ?? m.cols}×${plan?.rows ?? m.rows} ${ids}`;
}

export function items(doc: Doc, plans: Record<string, MarkerPlan>): Item[] {
  return doc.features.flatMap((f, slot) => {
    const req = planRequest(doc, f);
    return req ? [{ f, req, plan: plans[f.id], key: JSON.stringify(req), slot }] : [];
  });
}
