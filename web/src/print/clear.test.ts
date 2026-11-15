import { describe, expect, it } from "vitest";
import { clearRequest, parseClear, snap, type ClearBox } from "./clear";

const box = (preset: string, page: number): ClearBox => ({ id: `${preset}${page}`, preset, page, x_mm: 10, y_mm: 20, w_mm: 30, h_mm: 40 });

describe("print margins and keep-clear boxes", () => {
  it("nothing typed and no box add nothing to the request", () => {
    expect(clearRequest({}, [], "p")).toEqual({});
  });

  it("only the typed sides and only this preset's boxes go out", () => {
    const got = clearRequest({ top: 60, left: 0 }, [box("p", 0), box("q", 1), box("p", 2)], "p");
    expect(got.margins_mm).toEqual({ top: 60, left: 0 });
    expect(got.keep_clear).toEqual([{ page: 0, x_mm: 10, y_mm: 20, w_mm: 30, h_mm: 40 }, { page: 2, x_mm: 10, y_mm: 20, w_mm: 30, h_mm: 40 }]);
  });

  it("stored junk is dropped field by field", () => {
    expect(parseClear("not json")).toEqual({ margins: {}, boxes: [] });
    expect(parseClear(null)).toEqual({ margins: {}, boxes: [] });
    const raw = JSON.stringify({ v: 1, margins: { top: 5, right: -1, bottom: "x" }, boxes: [box("p", 0), { ...box("p", 1), w_mm: 0 }, { ...box("p", 2), page: -1 }] });
    expect(parseClear(raw)).toEqual({ margins: { top: 5 }, boxes: [box("p", 0)] });
  });

  it("a drawn box snaps to 0.5 mm", () => {
    expect([snap(10.24), snap(10.26), snap(-0.2)].map((v) => v + 0)).toEqual([10, 10.5, 0]);
  });
});
