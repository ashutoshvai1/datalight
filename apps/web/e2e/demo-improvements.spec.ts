import { expect, test } from "@playwright/test";

test("Docs can be opened without depending on an analysis", async ({
  page,
}) => {
  await page.route("**/api/v1/system", (route) =>
    route.fulfill({
      json: {
        run: null,
        source: null,
        source_error: null,
        model_status: "unavailable",
      },
    }),
  );
  await page.goto("/docs");
  await expect(
    page.getByRole("heading", { name: "Docs", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Mean absolute error/i).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/docs-mobile.png",
    fullPage: true,
  });
});

test("uploaded CSV, exclusion, rule, conversation, and historical chart", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.MODEL_QA !== "1",
    "Uses the isolated synthetic model fixture",
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "New analysis", exact: true }).click();
  await expect(
    page
      .getByText(
        "Illuminate your data. Talk to it. Evidence centric analysis. Your data stays private.",
      )
      .last(),
  ).toBeVisible();
  const csv = ["sample,temperature,pressure,notes,faultNumber,simulationRun"];
  for (let index = 0; index < 1500; index++) {
    csv.push(
      `${(index % 71) + 1},${index < 600 ? 20 + Math.sin(index / 6) : 90 + Math.sin(index / 6)},${index * 10},synthetic row,0,1`,
    );
  }
  await page.getByLabel("Upload CSV", { exact: true }).setInputFiles({
    name: "synthetic-upload.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv.join("\n")),
  });
  await expect(page.getByText("Selected: synthetic-upload.csv")).toBeVisible();
  await page.getByLabel("Initial samples").fill("100");
  await page.getByLabel("Seconds between batches").fill("0.6");
  await page
    .getByRole("button", { name: "Build understanding report" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Monitoring setup", exact: true }),
  ).toBeVisible();
  const run = (await (await request.get("/api/v1/system")).json()).run;
  expect(run.config.reader_mode).toBe("rows");
  await expect(
    page.getByText("Full pairwise correlation matrix", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("details").filter({
      has: page.getByText("Full pairwise correlation matrix", {
        exact: true,
      }),
    }),
  ).toHaveAttribute("open", "");
  await page.getByRole("checkbox", { name: "pressure", exact: true }).check();
  await page
    .getByRole("button", { name: "Save monitoring setup", exact: true })
    .click();
  await expect(
    page.getByText("Monitoring setup saved", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Describe a simple rule", { exact: true })
    .fill("Flag fault if temperature exceeds 80");
  await page.getByRole("button", { name: "Propose rule", exact: true }).click();
  await expect(
    page.getByText("Flag Fault Suspected when temperature > 80."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Apply rule", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Remove rule for temperature" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/upload-config-desktop.png",
    fullPage: true,
  });
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: "pressure", exact: true }),
  ).toBeChecked();
  await expect(
    page.getByRole("button", { name: "Remove rule for temperature" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Monitoring", exact: true }).click();
  await expect(page.getByLabel("Trend channel").locator("option")).toHaveCount(
    1,
  );
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json())
          .rows_processed,
    )
    .toBeGreaterThan(100);
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json())
          .rows_processed,
    )
    .toBeGreaterThan(500);
  const history = page.getByRole("scrollbar", { name: "Monitoring history" });
  await history.focus();
  await history.press("Home");
  await expect(history).toHaveAttribute("aria-valuenow", "2");
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json())
          .rows_processed,
    )
    .toBeGreaterThan(800);
  await expect(history).toHaveAttribute("aria-valuenow", "2");
  await page.getByRole("button", { name: "Latest", exact: true }).click();
  const locked = await request.post(
    `/api/v1/runs/${run.id}/monitoring-config`,
    { data: { excluded_channel_ids: [], rule_ids: [] } },
  );
  expect(locked.status()).toBe(409);
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json()).status,
      { timeout: 30000 },
    )
    .toBe("completed");
  await expect(history).toHaveAttribute("aria-valuenow", "14");
  const plot = page.getByRole("img", {
    name: "Incoming channel values and forecast",
  });
  await plot.hover();
  await page.mouse.wheel(-150, 0);
  await expect(history).toHaveAttribute("aria-valuenow", "13");
  await page.getByRole("button", { name: "Latest", exact: true }).click();
  await expect(history).toHaveAttribute("aria-valuenow", "14");
  const trace = await (
    await request.get(
      `/api/v1/runs/${run.id}/trace?channel_id=c001&batch_window=3`,
    )
  ).json();
  expect(trace.points).toHaveLength(300);
  expect(trace.points[0].row).toBe(1201);
  const past = await (
    await request.get(
      `/api/v1/runs/${run.id}/trace?channel_id=c001&batch_window=3&end_batch=3`,
    )
  ).json();
  expect(past.points[0].row).toBe(101);
  expect(past.points.at(-1).row).toBe(400);
  expect(
    new Set(past.points.map((point: { sequence: number }) => point.sequence))
      .size,
  ).toBe(1);
  const decisions = await (
    await request.get(`/api/v1/runs/${run.id}/decisions`)
  ).json();
  expect(
    decisions.some(
      (decision: { decision: { rule_matches: unknown[] } }) =>
        decision.decision.rule_matches.length > 0,
    ),
  ).toBeTruthy();
  const card = page.locator(".decision-card").filter({
    has: page.getByRole("heading", {
      name: "Samples 1401–1500",
      exact: true,
    }),
  });
  await expect(card).toBeVisible();
  await card
    .getByRole("button", { name: "Evidence 1", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("dialog", { name: "Supporting evidence" }),
  ).toContainText('"threshold": 80');
  await page
    .getByRole("button", { name: "Close evidence", exact: true })
    .click();
  await card.getByRole("button", { name: "Question", exact: true }).click();
  await card.getByLabel("Your question").fill("Why was this batch flagged?");
  await card.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(card.getByText(/Synthetic answer/).first()).toBeVisible();
  await card
    .getByLabel("Continue the conversation")
    .fill("How does that compare with the reference?");
  await card
    .getByRole("button", { name: /Ask question|Send follow-up/ })
    .click();
  await expect(card.getByText(/1 previous exchange/)).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Latest", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("scrollbar", { name: "Monitoring history" }),
  ).toHaveAttribute("aria-valuenow", "14");
  await page
    .locator(".decision-card")
    .first()
    .getByText("Review history & questions", { exact: true })
    .click();
  await expect(
    page
      .locator(".decision-card")
      .first()
      .getByText(/1 previous exchange/),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/upload-monitoring-desktop.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
