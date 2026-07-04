import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // HR-05 (2026-07 hardening sprint) ESLint baseline for CI, per
    // docs/sprints/2026-07_hardening/03-ci-pipeline-spec.md §2:
    // "the error channel is reserved for crash-class findings." The only crash-class
    // rule left as an error is `react-hooks/rules-of-hooks` (the 2 remaining errors
    // are HR-06's job — do NOT silence them here). Every other rule that was firing
    // as an error on the pre-existing portal code is downgraded to `warn` so it is
    // still surfaced (never lost) but does not gate CI. These warnings — especially
    // the React-19-compiler advisories (static-components / purity / immutability) and
    // no-unescaped-entities — are tracked for a future portal lint-cleanup ticket.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react/no-unescaped-entities": "warn",
      "react-hooks/static-components": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/immutability": "warn",
    },
  },
]);

export default eslintConfig;
