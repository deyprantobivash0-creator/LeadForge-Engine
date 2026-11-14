import { test, expect } from "./helpers/test.js";
import { api, login } from "./helpers/auth.js";
import { currentDecision, decisionResponse, recordedDecision } from "./fixtures/decisionHistory.js";

/** @param {import('@playwright/test').Page} page */
async function mockWorkspace(page, { empty = false, mixed = false, fail = "", holdRead = false } = {}) {
  /** @type {{records: ReturnType<typeof recordedDecision>[], reads: number, posts: number, pages: number[], release: () => void, releaseRead: () => void, hold: boolean, fail: string, holdRead: boolean}} */
  const state = { records: empty ? [] : [7, 6, 5, 4, 3, 2, 1].map(recordedDecision), reads: 0, posts: 0, pages: [], release: () => {}, releaseRead: () => {}, hold: false, fail, holdRead };
  await page.addInitScript(() => localStorage.setItem("leadforge-workspace-1", "1"));
  await page.context().addCookies([{ name: "leadforge_csrf", value: "synthetic-decision-csrf", url: "http://127.0.0.1:8080" }]);
  const lead = { id: 1, organization_id: 1, company: "Synthetic Decision Lead", email: "synthetic@example.invalid", source: "fixture", status: "New", processing_status: "pending", current_analysis: null, created_at: currentDecision.generated_at };
  await page.route("**/api/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const simple = { "/api/auth/me": { id: 1, email: "synthetic@example.invalid", is_active: true }, "/api/organizations": [{ id: 1, name: "Synthetic workspace", slug: "synthetic", role: "owner" }], "/api/leads/": { items: [lead], total: 1, page: 1, page_size: 20, pages: 1 }, "/api/leads/1": lead }[path];
    if (simple) return route.fulfill({ json: simple });
    expect(request.headers()["x-organization-id"]).toBe("1");
    if (path === "/api/leads/1/opportunity-decision/change") {
      state.reads++;
      if (state.holdRead) { await new Promise(/** @param {(value: void | PromiseLike<void>) => void} resolve */ resolve => { state.releaseRead = resolve; }); state.holdRead = false; }
      if (state.fail === "initial") {
        state.fail = "";
        return route.fulfill({ status: 500, json: { error: { message: "INTERNAL_SCHEMA_DIAGNOSTIC" } } });
      }
      if (state.fail === "refresh" && state.posts > 0) {
        state.fail = "";
        return route.fulfill({ status: 500, json: { error: { message: "INTERNAL_SCHEMA_DIAGNOSTIC" } } });
      }
      return route.fulfill({ json: decisionResponse(state.records, mixed && state.posts === 0) });
    }
    if (path === "/api/leads/1/opportunity-decisions" && request.method() === "POST") {
      state.posts++;
      expect(request.headers()["x-csrf-token"]).toBe("synthetic-decision-csrf");
      expect(request.postDataJSON()).toEqual({});
      if (state.hold) await new Promise(/** @param {(value: void | PromiseLike<void>) => void} resolve */ resolve => { state.release = resolve; });
      const row = recordedDecision(8 + state.posts);
      state.records.unshift(row);
      if (state.fail === "post") {
        state.fail = "";
        return route.fulfill({ status: 500, json: { error: { message: "INTERNAL_SCHEMA_DIAGNOSTIC" } } });
      }
      return route.fulfill({ status: 201, json: row });
    }
    if (path === "/api/leads/1/opportunity-decisions") {
      const offset = Number(url.searchParams.get("offset"));
      expect(url.searchParams.get("limit")).toBe("5");
      state.pages.push(offset);
      return route.fulfill({ json: { items: state.records.slice(offset, offset + 5), total: state.records.length, offset, limit: 5 } });
    }
    throw new Error(`Unexpected synthetic decision request: ${path}`);
  });
  await page.goto("/leads");
  await page.getByRole("button", { name: "Open Synthetic Decision Lead details", exact: true }).filter({ visible: true }).click();
  return state;
}

test("real Decision Ledger flow stays passive until explicit recording and reflects a lifecycle change", async ({ page }, testInfo) => {
  test.setTimeout(150000);
  // Existing suite shares a real 10/min login budget. Never weaken it for QA.
  await new Promise(resolve => setTimeout(resolve, 61000));
  await login(page);
  const company = `Decision History ${Date.now()}`;
  const created = await api(page, "/api/leads/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company, email: `decision-${Date.now()}@example.com`, source: "p2c-fixture" }) });
  expect(created.status).toBe(200);
  const id = created.body.id;
  await page.goto("/leads");
  await page.getByLabel("Search leads", { exact: true }).fill(company);
  await page.getByLabel("Search leads", { exact: true }).press("Enter");
  await page.getByRole("button", { name: `Open ${company} details`, exact: true }).filter({ visible: true }).click();
  const region = page.getByRole("region", { name: "Revenue Brain decision history", exact: true });
  await expect(region.getByText("No recorded decisions yet", { exact: true })).toBeVisible();
  await region.getByRole("button", { name: "Refresh Revenue Brain", exact: true }).click();
  await expect(region.getByRole("button", { name: "Record current decision", exact: true })).toBeEnabled();
  expect((await api(page, `/api/leads/${id}/opportunity-decisions`)).body.total).toBe(0);
  await region.getByRole("button", { name: "Record current decision", exact: true }).click();
  await expect(region.locator(".decision-records > li")).toHaveCount(1);
  await expect(region.getByText("Unchanged", { exact: false }).first()).toBeVisible();
  const first = (await api(page, `/api/leads/${id}/opportunity-decisions`)).body.items[0];
  await page.getByLabel("Status", { exact: true }).selectOption("Meeting");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByText("Lead lifecycle updated.", { exact: true })).toBeVisible();
  await expect(region.getByText("Improved", { exact: false }).first()).toBeVisible();
  await region.getByRole("button", { name: "Record current decision", exact: true }).click();
  await expect(region.locator(".decision-records > li")).toHaveCount(2);
  /** @type {import('../src/types/revenueDecision').HistoryPage} */
  const after = (await api(page, `/api/leads/${id}/opportunity-decisions`)).body;
  expect(after.total).toBe(2);
  expect(after.items.find(row => row.id === first.id)).toEqual(first);
  await region.getByText("Inspect current reasons and evidence", { exact: true }).click();
  await expect(region.getByText("Neutral default · not an observed signal").first()).toBeVisible();
  for (const [width, height] of [[1440, 900], [1024, 900], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await region.getByRole("heading", { name: "Revenue Brain", exact: true }).scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(await page.getByRole("dialog").evaluate(panel => panel.scrollWidth <= panel.clientWidth + 1)).toBe(true);
    await testInfo.attach(`revenue-brain-${width}`, { body: await page.screenshot(), contentType: "image/png" });
  }
  await region.locator(".decision-records > li").first().getByText("Inspect recorded decision", { exact: true }).click();
  await region.locator(".decision-records > li").first().scrollIntoViewIfNeeded();
  await testInfo.attach("revenue-history-mobile", { body: await page.screenshot(), contentType: "image/png" });
});

test("mock current/history and canonical MIXED change remain truthful, accessible and responsive", async ({ page }) => {
  const state = await mockWorkspace(page, { mixed: true });
  const region = page.getByRole("region", { name: "Revenue Brain decision history", exact: true });
  await expect(region.getByRole("heading", { name: "Current computed decision", exact: true })).toBeVisible();
  await expect(region.getByText("Current · not a recorded snapshot", { exact: true })).toBeVisible();
  await expect(region.locator(".decision-direction")).toContainText("Mixed changes");
  await expect(region.getByText("+8 points", { exact: true })).toBeVisible();
  await expect(region.getByText("-5 percentage points", { exact: true })).toBeVisible();
  await expect(region.getByText(/Qualify → Prepare outreach/)).toBeVisible();
  const summary = region.getByText("Inspect current reasons and evidence", { exact: true });
  await summary.focus(); await page.keyboard.press("Enter");
  await expect(region.getByText("Stored estimate · not externally verified").first()).toBeVisible();
  await region.getByText("Inspect evidence changes", { exact: true }).click();
  const changes = region.getByRole("region", { name: "Changes since latest recording", exact: true });
  await expect(changes.getByText("Neutral default · not an observed signal")).toBeVisible();
  await expect(changes.getByText(/this factor is treated neutrally/)).toBeVisible();
  await region.locator(".decision-records > li").first().getByText("Inspect recorded decision", { exact: true }).click();
  await expect(region.locator(".decision-records > li").first()).toContainText("Decision generated:");
  await expect(region.locator(".decision-records > li").first()).toContainText("Decision recorded:");
  expect(state.posts).toBe(0); expect(state.pages).toEqual([]); expect(state.reads).toBe(1);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Open Synthetic Decision Lead details", exact: true }).filter({ visible: true })).toBeFocused();
});

test("mock history loads bounded next page in backend order without duplicate current or detail requests", async ({ page }) => {
  const state = await mockWorkspace(page);
  const region = page.getByRole("region", { name: "Revenue Brain decision history", exact: true });
  await expect(region.locator(".decision-records > li")).toHaveCount(5);
  await region.getByRole("button", { name: "Load more decisions", exact: true }).click();
  await expect(region.locator(".decision-records > li")).toHaveCount(7);
  await expect(region.getByRole("button", { name: "Load more decisions", exact: true })).toHaveCount(0);
  const timestamps = await region.locator(".decision-records > li > p > time").evaluateAll(nodes => nodes.map(node => node.getAttribute("datetime")));
  expect(timestamps).toEqual(state.records.map(row => row.recorded_at));
  expect(state.pages).toEqual([5]); expect(state.reads).toBe(1); expect(state.posts).toBe(0);
});

test("mock explicit recording sends CSRF once while in flight and permits a later deliberate record", async ({ page }) => {
  const state = await mockWorkspace(page, { empty: true });
  const region = page.getByRole("region", { name: "Revenue Brain decision history", exact: true });
  await expect(region.getByText("No recorded decisions yet", { exact: true })).toBeVisible();
  state.hold = true;
  await region.getByRole("button", { name: "Record current decision", exact: true }).click();
  const pending = region.getByRole("button", { name: "Recording decision…", exact: true });
  await expect(pending).toBeDisabled();
  await expect.poll(() => state.posts).toBe(1);
  await pending.evaluate(button => button.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  expect(state.posts).toBe(1);
  await expect(region.locator(".decision-records > li")).toHaveCount(0);
  state.hold = false; state.release();
  await expect(region.locator(".decision-records > li")).toHaveCount(1);
  await expect(region.getByRole("button", { name: "Record current decision", exact: true })).toBeEnabled();
  await region.getByRole("button", { name: "Record current decision", exact: true }).click();
  await expect(region.locator(".decision-records > li")).toHaveCount(2);
  expect(state.posts).toBe(2); expect(state.reads).toBe(3);
});

for (const fail of ["post", "refresh"]) {
  test(`mock ${fail} failure requires a read refresh and never leaks diagnostics or fakes history`, async ({ page }, testInfo) => {
    testInfo.annotations.push({ type: "expected-http", description: `500 /api/leads/1/${fail === "post" ? "opportunity-decisions" : "opportunity-decision/change"}` });
    testInfo.annotations.push({ type: "expected-browser-error", description: "Failed to load resource: the server responded with a status of 500" });
    const state = await mockWorkspace(page, { empty: true, fail });
    const region = page.getByRole("region", { name: "Revenue Brain decision history", exact: true });
    await expect(region.getByRole("button", { name: "Record current decision", exact: true })).toBeEnabled();
    await region.getByRole("button", { name: "Record current decision", exact: true }).click();
    await expect(region.getByRole("alert")).toContainText(fail === "post" ? "Recording was not confirmed" : "history could not refresh");
    await expect(region.getByRole("button", { name: "Record current decision", exact: true })).toBeDisabled();
    await expect(page.getByText("INTERNAL_SCHEMA_DIAGNOSTIC", { exact: false })).toHaveCount(0);
    await expect(region.locator(".decision-records > li")).toHaveCount(0);
    await region.getByRole("button", { name: "Refresh Revenue Brain", exact: true }).click();
    await expect(region.locator(".decision-records > li")).toHaveCount(1);
    await expect(region.getByRole("button", { name: "Record current decision", exact: true })).toBeEnabled();
    expect(state.posts).toBe(1);
  });
}

test("mock initial loading reserves space and a safe retry recovers without recording", async ({ page }, testInfo) => {
  testInfo.annotations.push({ type: "expected-http", description: "500 /api/leads/1/opportunity-decision/change" });
  testInfo.annotations.push({ type: "expected-browser-error", description: "Failed to load resource: the server responded with a status of 500" });
  const state = await mockWorkspace(page, { empty: true, fail: "initial", holdRead: true });
  const region = page.getByRole("region", { name: "Revenue Brain decision history", exact: true });
  await expect(region.getByText("Loading Revenue Brain…", { exact: true })).toBeVisible();
  expect(await region.locator(".decision-loading").evaluate(element => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(180);
  await expect(region.getByRole("button", { name: "Record current decision", exact: true })).toBeDisabled();
  state.releaseRead();
  await expect(region.getByRole("alert")).toContainText("Revenue Brain could not be loaded");
  await expect(page.getByText("INTERNAL_SCHEMA_DIAGNOSTIC", { exact: false })).toHaveCount(0);
  await region.getByRole("button", { name: "Retry Revenue Brain", exact: true }).click();
  await expect(region.getByText("No recorded decisions yet", { exact: true })).toBeVisible();
  expect(state.posts).toBe(0);
});
