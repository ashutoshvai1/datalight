import { expect, test } from "@playwright/test";

test("confidence progresses Low to High, preserves reviews, and handles legacy decisions", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const csv =
    "signal\n" + [...Array(100).fill("0"), ...Array(40).fill("7")].join("\n");
  const upload = await request.post("/api/v1/sources/upload", {
    multipart: {
      file: {
        name: "synthetic-confidence.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv),
      },
    },
  });
  expect(upload.ok()).toBeTruthy();
  const source = await upload.json();
  const created = await request.post("/api/v1/runs", {
    data: {
      source_id: source.id,
      initial_rows: 100,
      batch_rows: 9,
      interval: 60,
    },
  });
  expect(created.ok()).toBeTruthy();
  const run = await created.json();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json()).status,
    )
    .toBe("paused");
  await page.goto("/monitoring");
  await expect(
    page.getByRole("heading", { name: "Monitoring", exact: true }),
  ).toBeVisible();
  const summary = page.locator(".status-panel");
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(
    summary.getByText("Confidence: Low", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/confidence-low-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(
    summary.getByText("Confidence: High", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
  const latest = (
    await (await request.get(`/api/v1/runs/${run.id}/decisions`)).json()
  )[0];
  expect(latest.decision.confidence.level).toBe("high");
  await request.post(`/api/v1/findings/${latest.id}/reviews`, {
    data: {
      action: "override",
      reason: "Synthetic confidence review",
      replacement: "OK",
    },
  });
  await page.reload();
  await expect(
    summary.getByText("Confidence: High", { exact: true }),
  ).toBeVisible();
  await expect(summary).toContainText("Human assessment: OK");
  await summary
    .getByRole("button", { name: "Evidence 1", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Supporting evidence" }),
  ).toContainText("observed_persistence");
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.screenshot({
    path: "test-results/confidence-high-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/confidence-high-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("link", { name: "Decision log", exact: true }).click();
  await expect(
    page
      .locator(".decision-card")
      .first()
      .getByText("Confidence: High", { exact: true }),
  ).toBeVisible();
  // Compatibility fixtures alter only HTTP responses, never stored history.
  await page.route("**/api/v1/runs/*/decisions?*", async (route) => {
    const response = await route.fetch();
    const decisions = await response.json();
    for (const item of decisions) delete item.decision.confidence;
    await route.fulfill({ response, json: decisions });
  });
  await page.reload();
  await expect(
    page.getByText("Confidence not recorded", { exact: true }).first(),
  ).toBeVisible();
  await page.unrouteAll({ behavior: "wait" });
  await page.route("**/api/v1/runs/*/decisions?*", async (route) => {
    const response = await route.fetch();
    const decisions = await response.json();
    for (const item of decisions) {
      item.decision.status = "OK";
      item.decision.confidence = null;
    }
    await route.fulfill({ response, json: decisions });
  });
  await page.reload();
  await expect(page.locator(".decision-card").first()).toBeVisible();
  await expect(page.locator(".decision-confidence")).toHaveCount(0);
  expect(errors).toEqual([]);
});
