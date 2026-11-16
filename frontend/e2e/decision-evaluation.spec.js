import { currentDecision, decisionResponse } from "./fixtures/decisionHistory.js";
import { test, expect } from "./helpers/test.js";

/** @param {import('@playwright/test').Page} page @param {'empty'|'evidence'|'error'} mode */
async function workspace(page, mode) {
  const gate = { release: () => {} };
  const pending = new Promise(/** @param {(value: void | PromiseLike<void>) => void} resolve */ resolve => { gate.release = resolve; });
  await page.addInitScript(() => localStorage.setItem("leadforge-workspace-1", "1"));
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return route.fulfill({ json: { id: 1, email: "synthetic@example.invalid", is_active: true } });
    if (path === "/api/organizations") return route.fulfill({ json: [{ id: 1, name: "Synthetic evaluation", slug: "synthetic", role: "owner" }] });
    expect(route.request().headers()["x-organization-id"]).toBe("1");
    if (path === "/api/leads/") return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20, pages: 0 } });
    if (path === "/api/dashboard/decision-evaluation") {
      if (mode === "error") { await pending; return route.fulfill({ status: 500, json: { detail: "PRIVATE_SYNTHETIC_EVALUATION" } }); }
      const counts = mode === "empty" ? { eligible: 0, evaluated: 0, pending: 0, positive: 0, negative: 0, inconclusive: 0 } : { eligible: 3, evaluated: 2, pending: 1, positive: 1, negative: 0, inconclusive: 1 };
      return route.fulfill({ json: { ...counts, policy_version: "latest_observation_v1", window: "all_time", coverage: mode === "empty" ? null : 2 / 3, evidence_context: mode === "empty" ? "No outcome evidence" : "Limited evidence", categories: [{ ...counts, recommendation: "QUALIFY" }] } });
    }
    if (path === "/api/dashboard/decision-evaluation/evidence") return route.fulfill({ json: { items: [{ decision_id: "synthetic-decision", lead_id: 1, recommendation: "QUALIFY", decision_recorded_at: "2026-11-01T00:00:00Z", outcome_id: null, kind: null, observed_at: null, outcome_recorded_at: null }], offset: 0, limit: 20, has_more: false } });
    if (path === "/api/leads/1") return route.fulfill({ json: { id: 1, organization_id: 1, company: "Synthetic evaluation lead", email: "synthetic@example.invalid", source: "fixture", status: "New", processing_status: "pending", current_analysis: null, created_at: currentDecision.generated_at } });
    if (path === "/api/leads/1/opportunity-decision/change") return route.fulfill({ json: decisionResponse([]) });
    throw new Error(`Unexpected synthetic evaluation request: ${path}`);
  });
  await page.goto("/ai");
  await page.getByText("Inspect decision evaluation", { exact: true }).click();
  return { panel: page.getByRole("region", { name: "Decision evaluation", exact: true }), release: gate.release };
}

test("evaluation empty state is honest and does not fabricate percentages", async ({ page }) => {
  const { panel } = await workspace(page, "empty");
  await expect(panel.getByText("No outcome evidence", { exact: true })).toBeVisible();
  await expect(panel.getByText(/No outcome evidence has been recorded yet/)).toBeVisible();
  await expect(panel.getByText("0 of 0", { exact: true })).toBeVisible();
  await expect(panel).not.toContainText("0%");
});

test("evaluation shows sample counts categories pending and trace identifiers", async ({ page }) => {
  const { panel } = await workspace(page, "evidence");
  await expect(panel.getByText("2 of 3", { exact: true })).toBeVisible();
  await expect(panel.getByText("Limited evidence", { exact: true })).toBeVisible();
  await expect(panel).toContainText("Outcome pending: 1. Positive evidence: 1. Negative evidence: 0. Inconclusive: 1.");
  await expect(panel.getByRole("row", { name: /QUALIFY/ })).toContainText("2 / 3");
  await panel.getByRole("button", { name: "Inspect underlying evidence" }).click();
  await expect(panel).toContainText("synthetic-decision");
  await panel.getByRole("button", { name: "Inspect lead 1 decisions and outcomes" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("region", { name: "Revenue Brain decision history", exact: true })).toBeVisible();
});

test("evaluation loading and failure expose no fabricated metrics or internal diagnostics", async ({ page }, info) => {
  info.annotations.push({ type: "expected-http", description: "500 /api/dashboard/decision-evaluation" });
  info.annotations.push({ type: "expected-browser-error", description: "Failed to load resource: the server responded with a status of 500" });
  const { panel, release } = await workspace(page, "error");
  await expect(panel.getByRole("status")).toContainText("Loading decision evaluation");
  release();
  await expect(panel.getByRole("alert")).toContainText("could not be loaded");
  await expect(panel).not.toContainText("PRIVATE_SYNTHETIC_EVALUATION");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Refresh evaluation" })).toBeEnabled();
});
