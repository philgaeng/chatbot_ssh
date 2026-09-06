// SPDX-License-Identifier: Apache-2.0

/**
 * HR-07's image-upload item, as far as it goes without a filed case (QA-04d).
 *
 * ⚠ **Partial, and the boundary is the application's, not the harness's.** Attaching a file
 * outside a case does **not** upload it: the webchat holds it and says so — *"Your file is
 * held here until you select a grievance in the status check flow. It will upload
 * automatically once a case is selected."* (measured 2026-09-06: zero `/upload-files`
 * requests). So the picker, the preview and the hold-and-explain behaviour are covered here;
 * **the upload itself needs an intake driven to a case**, which runs the classifier and
 * therefore costs money per run — the constraint that shapes this whole sub-ticket.
 *
 * What is deferred, and why, is in
 * `docs/sprints/2026-09_qa_automation/followups/webchat-items-needing-a-filed-case.md`.
 * ⭐ **The hold behaviour is worth a test on its own merits:** a complainant who attaches a
 * photo and is told nothing would reasonably believe it was sent.
 */
import { test, expect } from "@playwright/test";
import path from "node:path";

import { WEBCHAT_URL } from "../env";
import { captureScreenshot } from "../fixtures/artifacts";
import { composerOpen } from "./chat";

const SITE_PHOTO = path.join(__dirname, "..", "fixtures", "site-photo.png");

test("an attached photo is previewed, held, and explained — not silently dropped", async ({
  page,
}, testInfo) => {
  await page.goto(WEBCHAT_URL);

  const uploads: string[] = [];
  page.on("request", (r) => {
    if (/\/upload-(files|voice)/.test(r.url())) uploads.push(r.url());
  });

  await composerOpen(page);

  await page.locator('input[type="file"]').first().setInputFiles(SITE_PHOTO);

  // The preview is the complainant's only confirmation that the picker worked at all.
  await expect(page.getByText(path.basename(SITE_PHOTO))).toBeVisible();

  await page.getByRole("button", { name: "Send message" }).click({ force: true });

  await expect(
    page.getByText("held here until you select a grievance", { exact: false }),
  ).toBeVisible();

  // The other half of the claim: it really was held. A silent upload to no case would leave
  // an orphaned file, which is the class of bug HR-07's session work was about.
  expect(uploads, "nothing should upload before a case is selected").toEqual([]);

  await captureScreenshot(page, testInfo, "webchat-attachment-held");
});
