import { test, expect } from "./helpers/test.js";
import { currentDecision, recordedDecision, decisionResponse } from "./fixtures/decisionHistory.js";

/** @param {import('@playwright/test').Page} page @param {boolean} [fail] */
async function workspace(page, fail = false) {
  /** @type {import('../src/services/decisionOutcomeService').OutcomeRecord[]} */
  const outcomes = [];
  const records = [recordedDecision(1)];
  let posts = 0;
  await page.addInitScript(() => localStorage.setItem("leadforge-workspace-1", "1"));
  await page.context().addCookies([{ name: "leadforge_csrf", value: "synthetic-outcome", url: "http://127.0.0.1:8080" }]);
  const lead = { id: 1, organization_id: 1, company: "Synthetic Outcome Lead", email: "synthetic@example.invalid", source: "fixture", status: "New", processing_status: "pending", current_analysis: null, created_at: currentDecision.generated_at };
  await page.route("**/api/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const simple = { "/api/auth/me": { id: 1, email: "synthetic@example.invalid", is_active: true }, "/api/organizations": [{ id: 1, name: "Synthetic workspace", slug: "synthetic", role: "owner" }], "/api/leads/": { items: [lead], total: 1, page: 1, page_size: 20, pages: 1 }, "/api/leads/1": lead }[path];
    if (simple) return route.fulfill({ json: simple });
    expect(request.headers()["x-organization-id"]).toBe("1");
    if (path === "/api/leads/1/opportunity-decision/change") return route.fulfill({ json: decisionResponse(records) });
    if (path === `/api/leads/1/opportunity-decisions/${records[0].id}/outcomes`) {
      if (request.method() === "POST") {
        posts++;
        expect(request.headers()["x-csrf-token"]).toBe("synthetic-outcome");
        if (fail) return route.fulfill({ status: 500, json: { detail: "PRIVATE_SYNTHETIC_DIAGNOSTIC" } });
        /** @type {import('../src/services/decisionOutcomeService').OutcomeInput} */
        const value = request.postDataJSON();
        const row = { ...value, id: `synthetic-${posts}`, organization_id: 1, lead_id: 1, decision_id: records[0].id, recorded_by_user_id: 1, recorded_at: new Date().toISOString(), source: "manual_user_report" };
        outcomes.unshift(row);
        return route.fulfill({ status: 201, json: row });
      }
      return route.fulfill({ json: { items: outcomes, total: outcomes.length, limit: 20, offset: 0, effectiveness: outcomes.length ? "Positive outcome" : "Outcome pending" } });
    }
    throw new Error(`Unexpected synthetic outcome request: ${path}`);
  });
  await page.goto("/leads");
  await page.getByRole("button", { name: "Open Synthetic Outcome Lead details", exact: true }).filter({ visible: true }).click();
  await page.getByText("Inspect recorded decision", { exact: true }).click();
  await page.getByText("Outcome evidence for this decision", { exact: true }).click();
  return { outcomes, posts: () => posts };
}

function observedTime() {
  const now = new Date(Date.now() - 60000);
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

test("outcome empty state, explicit recording, safe note and persistent chronological evidence", async ({ page }) => {
  const state = await workspace(page);
  const panel = page.getByRole("region", { name: "Decision outcome evidence", exact: true });
  await expect(panel.getByText("No outcomes recorded for this decision.")).toBeVisible();
  await expect(panel.getByText("Outcome pending", { exact: true })).toBeVisible();
  expect(state.posts()).toBe(0);
  await panel.getByRole("combobox").selectOption("Meeting");
  await panel.getByLabel("Observed at (your local time)").fill(observedTime());
  await panel.getByLabel("Outcome evidence note (optional)").fill("<script>synthetic evidence</script>");
  await panel.getByRole("button", { name: "Confirm outcome", exact: true }).click();
  await expect(panel.getByText("Positive outcome", { exact: true })).toBeVisible();
  await expect(panel.getByText("<script>synthetic evidence</script>", { exact: true })).toBeVisible();
  expect(state.posts()).toBe(1);
  await expect(panel.locator("script")).toHaveCount(0);
  await panel.getByRole("button", { name: "Confirm outcome", exact: true }).click();
  await expect(panel.locator("ol > li")).toHaveCount(2);
  expect(state.outcomes[0].recorded_at >= state.outcomes[1].recorded_at).toBe(true);
  await panel.getByRole("button", { name: "Refresh outcomes" }).click();
  await expect(panel.locator("ol > li")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Recorded decision history" }).locator(".decision-records > li")).toHaveCount(1);
});

test("invalid outcome observation is blocked without a write", async ({ page }) => {
  const state = await workspace(page);
  const panel = page.getByRole("region", { name: "Decision outcome evidence", exact: true });
  await expect(panel.getByText("Outcome pending", { exact: true })).toBeVisible();
  await panel.getByLabel("Observed at (your local time)").fill("2000-01-01T10:00");
  await panel.getByRole("button", { name: "Confirm outcome", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("after this decision");
  expect(state.posts()).toBe(0);
});

test("unconfirmed outcome write requires explicit refresh and never fabricates evidence", async ({ page }, testInfo) => {
  testInfo.annotations.push({ type: "expected-http", description: "500 /api/leads/1/opportunity-decisions/" });
  testInfo.annotations.push({ type: "expected-browser-error", description: "Failed to load resource: the server responded with a status of 500" });
  const state = await workspace(page, true);
  const panel = page.getByRole("region", { name: "Decision outcome evidence", exact: true });
  await expect(panel.getByText("Outcome pending", { exact: true })).toBeVisible();
  await panel.getByLabel("Observed at (your local time)").fill(observedTime());
  await panel.getByRole("button", { name: "Confirm outcome", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Recording was not confirmed");
  await expect(panel.getByRole("button", { name: "Confirm outcome", exact: true })).toBeDisabled();
  await expect(panel.locator("ol > li")).toHaveCount(0);
  await expect(page.getByText("PRIVATE_SYNTHETIC_DIAGNOSTIC", { exact: false })).toHaveCount(0);
  expect(state.posts()).toBe(1);
  await panel.getByRole("button", { name: "Refresh outcomes" }).click();
  await expect(panel.getByRole("button", { name: "Confirm outcome", exact: true })).toBeEnabled();
});
