// SPDX-License-Identifier: Apache-2.0

/**
 * Tier-1 flow (QA-04c): Reports → generate an XLSX, and share it.
 *
 * ⭐ **The download is the assertion.** Nothing else in the suite proves the export path end to
 * end: `openpyxl` runs server-side, the file is streamed through the Next proxy, and the
 * browser saves it. A unit test can check the row projection; only a browser can catch a
 * proxy that mangles a binary body or a `Content-Disposition` the browser will not honour.
 * ⚠ The proxy passes bodies through as streams (`app/api/v1/[...path]/route.ts`), which is
 * exactly the code path most likely to break on a Next upgrade and least likely to be noticed.
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { workbookStrings } from "../fixtures/xlsx";
import { createReportShare, OFFICERS } from "../fixtures/seed";

/** XLSX files are ZIP archives; every one starts with the local-file-header magic `PK\x03\x04`. */
const ZIP_MAGIC = Buffer.from([0x50, 0x4b, 0x03, 0x04]);

/**
 * Pick a district in the Locations filter.
 *
 * The control is a native `<select>` holding the whole location tree (~500 options), so it is
 * matched by the option's own label rather than by index — an index would silently drift the
 * day a district is added.
 */
async function selectLocation(page: import("@playwright/test").Page, district: string): Promise<void> {
  const locations = page.locator("select").filter({ has: page.locator(`option:text-is("${district}")`) });
  await expect(locations, `no Locations select offering "${district}"`).toHaveCount(1);
  await locations.selectOption({ label: district });
}

test("reports → export all data as XLSX", async ({ page, asOfficer }, testInfo) => {
  // Generous, because the export builds a workbook server-side and streams it back. The
  // suite's 30 s default is the wrong budget and a timeout here would read as "export broken".
  test.setTimeout(90_000);

  await asOfficer(OFFICERS.admin);
  await page.goto("/reports");

  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();

  // ⚠ **Narrow the filter first, or this test is a coin flip.** The export refuses anything
  // over `report_limits.max_export_rows` (100) with *"Export limited to 100 rows. Narrow
  // filters."* — a real product rule, and a busy database trips it: measured 2026-09-06, this
  // dev stack held 336 tickets and the unfiltered export returned HTTP 400.
  //
  // Sunsari is the filter chosen deliberately: the seed puts tickets there, and **nothing this
  // suite creates does** (`fixtures/ticket.ts` writes to `P1_MOR`), so the count stays small on
  // a dev box that has been running for months as well as on a fresh CI seed.
  await selectLocation(page, "Sunsari");

  // ⚠ A generous timeout, and it is not padding. The export runs openpyxl over the whole
  // visible ticket set server-side and streams the file back; measured on this stack it is
  // several seconds and grows with the data. The suite's 10 s `expect` default is the wrong
  // budget for it, and a flake here would read as "export is broken".
  const downloadPromise = page.waitForEvent("download", { timeout: 60_000 });
  await page.getByRole("button", { name: "Export all data (XLSX)" }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);

  // Assert the bytes, not just that a download event fired: a 0-byte file, or an HTML error
  // page saved under an .xlsx name, would satisfy the event and fail the officer.
  const file = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(file);
  const { readFile } = await import("node:fs/promises");
  const bytes = await readFile(file);

  expect(bytes.length, "an empty export is a failed export").toBeGreaterThan(1_000);
  expect(
    bytes.subarray(0, 4).equals(ZIP_MAGIC),
    "an .xlsx that is not a ZIP archive is an error page wearing a spreadsheet's name",
  ).toBe(true);

  // GRM-118: what was done and who did it are in the workbook, as headers. That a resolved row is
  // filled is pinned by tests/ticketing/test_report_resolution_columns.py — the cases this suite
  // resolves live in Morang, and a long-running dev box holds more there than the 100-row export cap.
  const strings = workbookStrings(bytes);
  for (const header of ["Resolution action", "Resolved by", "Resolution action (national)"]) {
    expect(strings, `the export should carry the "${header}" column`).toContain(header);
  }

  await testInfo.attach("report-export", { path: file });
  await captureScreenshot(page, testInfo, "flow-reports-export");
});

test("reports → create share links and open the public one", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await page.goto("/reports");

  // ⚠ This button is what GRM-071 broke: it returned HTTP 500 on any database where nobody had
  // shared a report before. It is covered here through the UI as well as at the service layer
  // (tests/ticketing/test_report_shares.py) because the two failed differently — the service
  // raised, and the officer saw only a generic failure.
  await page.getByRole("button", { name: "Copy report links" }).click();

  // The links land in the page rather than only on the clipboard, which is what makes this
  // assertable without granting clipboard permissions.
  await expect(page.getByText("/reports/public/", { exact: false }).first()).toBeVisible({
    timeout: 20_000,
  });

  await captureScreenshot(page, testInfo, "flow-reports-share");
});

test("a shared report opens on both its links — internal and public", async ({
  page,
  asOfficer,
}, testInfo) => {
  // Made through the API rather than by clicking, so this spec tests the *views* rather than
  // re-testing the button the previous test already drives.
  const { internalToken, publicToken } = await createReportShare();

  await asOfficer(OFFICERS.admin);

  await page.goto(`/reports/view/${internalToken}`);
  await expect(page.getByText("e2e smoke share", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Something went wrong")).toBeHidden();
  await captureScreenshot(page, testInfo, "flow-report-internal-view");

  await page.goto(`/reports/public/${publicToken}`);
  await expect(page.getByText("e2e smoke share", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Something went wrong")).toBeHidden();
  await captureScreenshot(page, testInfo, "flow-report-public-view");

  // ⭐ **The two views are not the same report, and that is the point of having two.** The
  // public one is projected through PUBLIC_REPORT_COLUMNS; the internal one through
  // ALL_DATA_EXPORT_COLUMNS. A share link handed to a complainant that rendered the internal
  // projection would be a disclosure, so the columns differing is the security property —
  // asserted here as "the public view is not simply the internal one".
  // ⚠ Wait for content before measuring. The first version read `innerText` straight after
  // `goto` and got 91 characters — the loading state — which made the internal view look
  // *smaller* than the public one and failed for the opposite of the real reason.
  const publicText = (await page.locator("body").innerText()).length;

  await page.goto(`/reports/view/${internalToken}`);
  await expect(page.getByText("e2e smoke share", { exact: false }).first()).toBeVisible();
  const internalText = (await page.locator("body").innerText()).length;
  expect(
    internalText,
    "the internal view should carry more than the public one — if they match, the public " +
      "projection may not be applied",
  ).toBeGreaterThan(publicText);
});

test("an invalid report token renders an error state rather than crashing", async ({
  page,
  asOfficer,
}) => {
  await asOfficer(OFFICERS.admin);
  await page.goto("/reports/public/not-a-real-token");

  await expect(page.getByText("Something went wrong")).toBeHidden();
  await expect(page.getByText("404", { exact: false }).first()).toBeVisible();
});
