import { expect, test } from "@playwright/test";

test("setup, paused report, sample chart, review and end of file", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "New analysis", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Understand first. Monitor next." }),
  ).toBeVisible();
  await expect(page.getByLabel("Initial samples")).toHaveValue("500");
  await expect(page.getByLabel("Seconds between batches")).toHaveValue("10");
  await page.getByLabel("Seconds between batches").fill("0.2");
  await page.screenshot({
    path: "test-results/setup-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Build understanding report" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Channel profiles" }),
  ).toBeVisible();
  const run = (await (await request.get("/api/v1/system")).json()).run;
  expect(run.status).toBe("paused");
  expect(run.rows_processed).toBe(500);
  await expect(
    page.getByRole("button", { name: "signal_a", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Inspect evidence", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Supporting evidence" }),
  ).toContainText('"mean"');
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.screenshot({
    path: "test-results/understanding-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Monitoring", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeEnabled();
  await page.reload();
  expect(
    (await (await request.get(`/api/v1/runs/${run.id}`)).json()).rows_processed,
  ).toBe(500);
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json())
          .rows_processed,
    )
    .toBeGreaterThan(500);
  // Pause through the API before a fast synthetic replay finishes, then verify the UI state.
  await request.post(`/api/v1/runs/${run.id}/control`, {
    data: { action: "pause" },
  });
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Accept", exact: true }).first(),
  ).toBeVisible();
  const card = page.locator(".decision-card").first();
  await card.getByRole("button", { name: "Override", exact: true }).click();
  await card.getByLabel("Your name").fill("Browser QA");
  await card.getByLabel("Override reason").fill("Synthetic operator review.");
  await card
    .getByRole("combobox", { name: "Human assessment", exact: true })
    .selectOption("Fault Suspected");
  await card.getByRole("button", { name: "Save review" }).click();
  await expect(
    card
      .getByText("Human assessment: Fault Suspected", { exact: true })
      .first(),
  ).toBeVisible();
  await card.getByRole("button", { name: "Question", exact: true }).click();
  await expect(card.getByLabel("Your name")).toHaveValue("Browser QA");
  await card
    .getByLabel("Your question")
    .fill("Why did the automated rule choose this status?");
  await card.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(
    card.getByText(/Model interpretation is disabled/),
  ).toBeVisible();
  await page.reload();
  await expect(
    page
      .locator(".decision-card")
      .first()
      .getByText("Human assessment: Fault Suspected", { exact: true })
      .first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json()).status,
    )
    .toBe("completed");
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Trend channel").selectOption("c002");
  const trace = await (
    await request.get(`/api/v1/runs/${run.id}/trace?channel_id=c002`)
  ).json();
  expect(trace.points).toHaveLength(1000);
  expect(
    trace.points.some((p: { forecast: number | null }) => p.forecast !== null),
  ).toBeTruthy();
  const decisions = await (
    await request.get(`/api/v1/runs/${run.id}/decisions`)
  ).json();
  expect(decisions).toHaveLength(11);
  expect(
    decisions.some(
      (d: { decision: { status: string } }) =>
        d.decision.status === "Fault Suspected",
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/monitoring-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Decision log", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Decision log", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".decision-card")).toHaveCount(11);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/log-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
