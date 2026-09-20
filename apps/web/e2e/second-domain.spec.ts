import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";

test("web-service CSV upload, reviewed rule, replay and cited discussion", async ({ page, request }) => {
  test.skip(process.env.MODEL_QA !== "1", "Requires the isolated synthetic model fixture");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "New analysis", exact: true }).click();
  await page.getByLabel("Upload CSV", { exact: true }).setInputFiles(
    fileURLToPath(new URL("../../../tests/fixtures/demo_web_service.csv", import.meta.url)),
  );
  await expect(page.getByText("Selected: demo_web_service.csv")).toBeVisible();
  await expect(page.getByLabel("Initial samples")).toHaveValue("500");
  await page.getByLabel("Seconds between batches").fill("1");
  await page.getByRole("button", { name: "Build understanding report" }).click();
  await expect(page.getByRole("heading", { name: "Monitoring setup", exact: true })).toBeVisible();
  const run = (await (await request.get("/api/v1/system")).json()).run;
  expect(run.config.reader_mode).toBe("rows");
  const report = await (await request.get(`/api/v1/runs/${run.id}/report`)).json();
  expect(report.profiles).toHaveLength(4);
  await page.getByLabel("Describe a simple rule", { exact: true })
    .fill("Flag a fault if p95_latency_ms exceeds 400");
  await page.getByRole("button", { name: "Propose rule", exact: true }).click();
  await expect(page.getByText("Flag Fault Suspected when p95_latency_ms > 400.")).toBeVisible();
  expect((await (await request.get(`/api/v1/runs/${run.id}`)).json()).config.rules).toEqual([]);
  await page.getByRole("button", { name: "Apply rule", exact: true }).click();
  await expect(page.getByRole("button", { name: "Remove rule for p95_latency_ms" })).toBeVisible();
  await page.screenshot({ path: "test-results/second-domain-understanding.png", fullPage: true });
  await page.getByRole("link", { name: "Monitoring", exact: true }).click();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect.poll(async () =>
    (await (await request.get(`/api/v1/runs/${run.id}`)).json()).status,
    { timeout: 30000 },
  ).toBe("completed");
  const decisions = await (await request.get(`/api/v1/runs/${run.id}/decisions`)).json();
  expect(decisions).toHaveLength(10);
  const healthy = decisions.filter((d: { decision: { row_end: number } }) => d.decision.row_end <= 700);
  expect(healthy).toHaveLength(2);
  for (const d of healthy) expect(d.decision.status).toBe("OK");
  const card = page.locator(".decision-card").filter({
    has: page.getByRole("heading", { name: "Samples 1401–1500", exact: true }),
  });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Question", exact: true }).click();
  await card.getByLabel("Your question").fill(
    "Which measurements support the flagged decision, and do they establish a cause?",
  );
  await card.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(card.getByText(/Synthetic answer/).first()).toBeVisible();
  await expect(card.getByText(/does not establish a physical cause/).first()).toBeVisible();
  const finding = decisions.find((d: { decision: { row_end: number } }) => d.decision.row_end === 1500);
  const answers = await (await request.get(`/api/v1/findings/${finding.id}/answers`)).json();
  expect(answers[0].status).toBe("succeeded");
  expect(answers[0].evidence_ids).toHaveLength(2);
  for (const id of answers[0].evidence_ids) {
    expect((await request.get(`/api/v1/evidence/${id}`)).ok()).toBeTruthy();
  }
  const evidenceButtons = card.getByRole("button", { name: /^Evidence \d+$/ });
  await evidenceButtons.last().click();
  await expect(page.getByRole("dialog", { name: "Supporting evidence" })).toContainText('"threshold": 400');
  await page.getByRole("button", { name: "Close evidence", exact: true }).click();
  await page.getByLabel("Trend channel").selectOption("c003");
  await page.screenshot({ path: "test-results/second-domain-monitoring.png", fullPage: true });
  await page.reload();
  await page.locator(".decision-card").first().getByText("Review history & questions", { exact: true }).click();
  await expect(page.locator(".decision-card").first().getByText(/Synthetic answer/).first()).toBeVisible();
  expect(errors).toEqual([]);
});
