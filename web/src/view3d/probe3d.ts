// What the 3D view hands the e2e probe (../probe.ts): set while it is
// mounted, null otherwise. Numbers, never a picture.
import type { Vec2 } from "../core/contract";
import type { Heights, HeightKey } from "./heights";

export interface Arrow3D {
  key: HeightKey;
  field: string;
  value: number;
  driven: boolean;
  /** the arrow's base in the scene (sketch frame, mm) and the z way it points */
  base3d: [number, number, number];
  dir: number;
  /** its base and its tip as client pixels, and its value box's client rect */
  base: Vec2;
  tip: Vec2;
  box: { x: number; y: number; w: number; h: number } | null;
}

export interface View3DProbe {
  /** the feature whose arrows are shown */
  feature: string | null;
  heights: Heights | null;
  arrows: Arrow3D[];
  /** solids drawn, by feature id */
  solids: Record<string, number>;
  /** face bodies drawn under face profiles (context) */
  faces: number;
  /** a scene point (mm) as client pixels */
  project: (x: number, y: number, z: number) => Vec2;
  /** the camera straight down on the feature in focus, its outline filling the view;
   *  `marks` false hides the arrows, dimension lines and value boxes (a clean top view) */
  top: (marks?: boolean) => void;
}

export const view3d: { probe: (() => View3DProbe) | null } = { probe: null };
