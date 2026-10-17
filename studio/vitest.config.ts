import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: { alias: [{ find: /^@bam\/ui/, replacement: path.resolve(import.meta.dirname, "packages/bam-ui/src") }] },
  test: { include: ["src/**/*.test.ts", "packages/*/src/**/*.test.ts"], environment: "node" },
});
