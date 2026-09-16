// SPDX-License-Identifier: Apache-2.0

import { defineConfig } from "vitest/config";
import path from "node:path";

// Minimal vitest config (HR-06 seed) — no plugins beyond path-alias resolution,
// matching tsconfig's "@/*" -> "./*" so tests can import lib/ modules the same
// way app code does. Tests are plain TS logic (no JSX/DOM), so "node" env only.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
