import { describe, expect, it } from "vitest";
import { create } from "zustand";
import { addShape, emptyDoc, newId, parseDoc, serialise, type Doc } from "../model/doc";
import { rectShape } from "../sketch/model";
import { studioAdapter } from "./adapter";
import { HOSTED_DEV, HOSTED_LIVE, hostedServer } from "./config";

/** useStudio's file half, and the view state beside the document. */
interface Fake { doc: Doc; camera: number; loadDoc: (d: Doc) => void; newDoc: () => void; edit: () => void; pan: () => void }
const fakeStudio = () => create<Fake>((set, get) => ({
  doc: emptyDoc("Plate"),
  camera: 0,
  loadDoc: (doc) => set({ doc }),
  newDoc: () => set({ doc: emptyDoc("Untitled") }),
  edit: () => set({ doc: addShape(get().doc, rectShape(newId(), 0, 0, 10, 10)) }),
  pan: () => set({ camera: get().camera + 1 }),
}));
/** the core's half: counts markDirty */
const fakeCore = () => { const c = { dirty: 0, markDirty: () => { c.dirty += 1; } }; return c; };

describe("the hosted files adapter", () => {
  it("the content is the saved file's text, as JSON", async () => {
    const store = fakeStudio();
    store.getState().edit();
    const { options } = studioAdapter(store);
    expect(options.contentType).toBe("application/json");
    expect(await options.getContent()).toBe(serialise(store.getState().doc));
  });

  it("setContent reads the bytes into the store, and the store gives the same bytes back", async () => {
    const source = fakeStudio();
    source.getState().edit();
    const text = serialise(source.getState().doc);
    const store = fakeStudio();
    const { options } = studioAdapter(store);
    await options.setContent(new Blob([text], { type: "application/json" }), null);
    expect(store.getState().doc).toEqual(parseDoc(text));
    expect(await options.getContent()).toBe(text);
  });

  it("an opened file's name is the document's name", async () => {
    const store = fakeStudio();
    const { options } = studioAdapter(store);
    const file = { name: "Forearm plate" } as Parameters<typeof options.setContent>[1];
    await options.setContent(new Blob([serialise(emptyDoc("Plate"))]), file);
    expect(store.getState().doc.name).toBe("Forearm plate");
  });

  it("the name a Save prompt answered is in the bytes, until a document is put in", async () => {
    const store = fakeStudio();
    const adapter = studioAdapter(store);
    adapter.nameNext("Forearm plate");
    expect(JSON.parse(String(await adapter.options.getContent())).name).toBe("Forearm plate");
    expect(store.getState().doc.name).toBe("Plate");
    await adapter.options.newDocument?.();
    expect(JSON.parse(String(await adapter.options.getContent())).name).toBe("Untitled");
  });

  it("the file autosave creates is named as the document is", () => {
    const store = fakeStudio();
    const adapter = studioAdapter(store);
    expect(adapter.options.documentName?.()).toBe("Plate");
    adapter.nameNext("Forearm plate");
    expect(adapter.options.documentName?.()).toBe("Forearm plate");
  });

  it("setContent refuses what is not a Studio file, and leaves the document", async () => {
    const store = fakeStudio();
    const before = store.getState().doc;
    const { options } = studioAdapter(store);
    await expect(options.setContent(new Blob(["{\"format\":\"other\"}"]), null)).rejects.toThrow(/arucostudio-web/);
    expect(store.getState().doc).toBe(before);
  });

  it("newDocument is the store's New", async () => {
    const store = fakeStudio();
    store.getState().edit();
    const { options } = studioAdapter(store);
    await options.newDocument?.();
    expect(store.getState().doc).toEqual(emptyDoc("Untitled"));
  });

  it("marks dirty on every document change, never on the view", () => {
    const store = fakeStudio();
    const core = fakeCore();
    studioAdapter(store).bind(core);
    store.getState().pan();
    expect(core.dirty).toBe(0);
    store.getState().edit();
    store.getState().edit();
    expect(core.dirty).toBe(2);
  });

  it("a document the core puts in (Open, New) is not an edit", async () => {
    const store = fakeStudio();
    const core = fakeCore();
    const adapter = studioAdapter(store);
    adapter.bind(core);
    await adapter.options.setContent(new Blob([serialise(emptyDoc("Opened"))]), null);
    await adapter.options.newDocument?.();
    expect(core.dirty).toBe(0);
    store.getState().edit();
    expect(core.dirty).toBe(1);
  });

  it("a change the store makes of its own (quiet) is not an edit", () => {
    const store = fakeStudio();
    const core = fakeCore();
    let filling = false;
    studioAdapter(store, () => filling).bind(core);
    filling = true;
    store.getState().edit();
    filling = false;
    expect(core.dirty).toBe(0);
    store.getState().edit();
    expect(core.dirty).toBe(1);
  });

  it("a failed open leaves the next edit marked", async () => {
    const store = fakeStudio();
    const core = fakeCore();
    const adapter = studioAdapter(store);
    adapter.bind(core);
    await Promise.resolve(adapter.options.setContent(new Blob(["not json"]), null)).catch(() => {});
    store.getState().edit();
    expect(core.dirty).toBe(1);
  });

  it("unbinding stops the marks", () => {
    const store = fakeStudio();
    const core = fakeCore();
    studioAdapter(store).bind(core)();
    store.getState().edit();
    expect(core.dirty).toBe(0);
  });

  it("the server: the env's, else local in dev and live in a build", () => {
    expect(hostedServer({ VITE_HOSTED_FILES_SERVER: "http://127.0.0.1:8793/", DEV: true })).toBe("http://127.0.0.1:8793");
    expect(hostedServer({ DEV: true })).toBe(HOSTED_DEV);
    expect(hostedServer({ DEV: false })).toBe(HOSTED_LIVE);
  });
});
