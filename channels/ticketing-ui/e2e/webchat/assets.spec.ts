// SPDX-License-Identifier: Apache-2.0

/**
 * HR-07's SRI item — *"SRI load-cleanliness in a real browser"* (QA-04d).
 *
 * HR-07 pinned `socket.io@4.7.4` and `exifr@7.1.3` with `integrity` + `crossorigin`. A wrong
 * hash does not warn: the browser **refuses the script silently**, and the feature it powers
 * simply stops existing. Static greps confirmed the attributes are present; only a browser can
 * confirm the hashes still match what the CDN serves.
 *
 * ⚠ **This spec deliberately does NOT stub the CDNs, which is an exception to rule 6a.10.**
 * The rule exists so a suite does not depend on a third party — but here the *dependency
 * itself* is the thing under test, and stubbing it would assert nothing. Every other spec that
 * meets a third party stubs it; this one is the one place the real fetch is the point.
 *
 * ⭐ **What writing it uncovered is bigger than the item.** Measured 2026-09-06 by blocking
 * egress in a browser: with the CDNs unreachable the page still renders its shell, but
 * `window.io`, `window.L` and `window.exifr` are all `undefined` — so real-time events, the map
 * picker and EXIF handling are gone from the **complainant** channel, on a service whose
 * production host is firewalled. Filed as `GRM-076`; not fixed here, because vendoring the
 * three libraries interacts with the SRI hardening this very item verifies.
 */
import { test, expect } from "@playwright/test";

import { WEBCHAT_URL } from "../env";

/** The three runtime libraries the page loads from outside this system. */
const PINNED = [
  { global: "io", host: "cdn.socket.io", what: "socket.io — real-time file/task status events" },
  { global: "L", host: "unpkg.com", what: "leaflet — the map pin picker" },
  { global: "exifr", host: "cdn.jsdelivr.net", what: "exifr — EXIF on uploaded photos" },
] as const;

test("the pinned third-party scripts load and define their globals", async ({ page }) => {
  const failures: string[] = [];
  page.on("console", (m) => {
    const t = m.text();
    // A subresource-integrity mismatch surfaces here and nowhere else.
    if (/integrity|Subresource Integrity/i.test(t)) failures.push(t);
  });

  await page.goto(WEBCHAT_URL);

  for (const lib of PINNED) {
    await expect
      .poll(() => page.evaluate((g) => typeof (window as never as Record<string, unknown>)[g], lib.global), {
        message:
          `window.${lib.global} is missing — ${lib.what}.\n` +
          `  Either ${lib.host} is unreachable from here (see GRM-076: the webchat hard-depends\n` +
          `  on three CDNs at runtime), or an integrity hash no longer matches what it serves,\n` +
          `  in which case the browser refused the script **silently**.`,
        timeout: 20_000,
      })
      .not.toBe("undefined");
  }

  expect(failures, "subresource integrity rejected a script").toEqual([]);
});

test("every pinned script tag still carries integrity and crossorigin", async ({ page }) => {
  await page.goto(WEBCHAT_URL);

  // The static half, asserted on the served document rather than on the file in the tree —
  // nginx aliases the working tree today, but that is a deployment detail, not a guarantee.
  const unprotected = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLScriptElement>("script[src^='https://']"))
      .filter((s) => !s.integrity || !s.crossOrigin)
      .map((s) => s.src),
  );

  expect(
    unprotected,
    "a remote script with no integrity attribute is an unpinned dependency on a page that " +
      "collects PII and SEAH reports — the finding HR-07 existed to close",
  ).toEqual([]);
});
