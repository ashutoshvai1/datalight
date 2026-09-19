import { expect, test } from "@playwright/test";

test("mounted CSV, replay controls, evidence, append-only review, and reload", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const created = await request.post("/api/v1/runs", {
    data: { initial_rows: 500, batch_rows: 100, interval: 3, threshold: 6 },
  });
  expect(created.status()).toBe(201);
  const run = await created.json();
  await page.goto("/understanding");
  await expect(
    page.getByRole("heading", { name: "Channel profiles" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /signal_a/ })).toBeVisible();
  await page.getByRole("button", { name: "Inspect evidence" }).click();
  await expect(
    page.getByRole("dialog", { name: "Supporting evidence" }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText('"median"');
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Resume", exact: true }),
  ).toBeEnabled();
  const paused = await (await request.get(`/api/v1/runs/${run.id}`)).json();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Resume", exact: true }),
  ).toBeEnabled();
  expect(
    (await (await request.get(`/api/v1/runs/${run.id}`)).json()).rows_processed,
  ).toBe(paused.rows_processed);
  await page.getByRole("link", { name: "Monitoring", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Watch the evidence evolve." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.getByRole("button", { name: "Fast-forward", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run.id}`)).json()).status,
    )
    .toBe("completed");
  const findings = await (
    await request.get(`/api/v1/runs/${run.id}/findings`)
  ).json();
  expect(
    findings.some((f: { category: string }) => f.category === "quality"),
  ).toBeTruthy();
  expect(
    findings.some((f: { category: string }) => f.category === "deviation"),
  ).toBeTruthy();
  await page.getByRole("link", { name: "Decision log", exact: true }).click();
  await page.getByLabel("Finding category").selectOption("assumption");
  await page.getByRole("button", { name: "Review conclusion" }).click();
  await page.getByLabel("Your name").fill("Browser QA");
  await page.getByLabel("Review action").selectOption("override");
  await page
    .getByLabel("Explanation", { exact: true })
    .fill("This fixture does not establish healthy operation.");
  await page
    .getByLabel("Replacement conclusion")
    .fill("Keep the reference provisional until operator validation.");
  await page.getByRole("button", { name: "Save review" }).click();
  await expect(page.getByRole("status")).toHaveText("Review saved");
  await expect(
    page.getByText(
      "Keep the reference provisional until operator validation.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.reload();
  await page.getByLabel("Finding category").selectOption("assumption");
  await page.getByRole("button", { name: "Review conclusion" }).click();
  await expect(
    page.getByText(
      "Keep the reference provisional until operator validation.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Provisional reference established" }),
  ).toBeVisible();
  const original = findings.find(
    (f: { category: string }) => f.category === "assumption",
  );
  const after = await (
    await request.get(`/api/v1/runs/${run.id}/findings?category=assumption`)
  ).json();
  expect(after[0]).toEqual(original);
  expect(errors).toEqual([]);
  await page.goto("/understanding");
  await expect(
    page.getByRole("heading", { name: "Channel profiles" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/understanding-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "A clearer picture of your data." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/understanding-mobile.png",
    fullPage: true,
  });
});
