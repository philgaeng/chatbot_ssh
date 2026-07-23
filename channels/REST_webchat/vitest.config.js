import { defineConfig } from "vitest/config";

// T3-03 seed harness for channels/REST_webchat/modules/.
//
// The webchat ships as plain ES modules loaded straight from index.html — there is no
// bundler and no build step, so this config deliberately stays minimal: vitest imports
// the very same files the browser does. Tests stub the browser surface they need
// (fetch/MediaRecorder/navigator) by hand rather than pulling in jsdom, because the
// modules under test are transport/ordering logic, not DOM rendering.
export default defineConfig({
  test: {
    environment: "node",
    include: ["modules/**/*.test.js"],
    exclude: ["node_modules/**"],
  },
});
