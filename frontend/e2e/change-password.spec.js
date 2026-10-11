// Isolated browser tests: every API request is intercepted, never sent to staging.
import { test, expect } from "@playwright/test";

const current = "synthetic current password";
const next = "synthetic replacement password";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("leadforge-workspace-1", "1"));
  await page.context().addCookies([{ name: "leadforge_csrf", value: "synthetic-csrf", url: "http://127.0.0.1:5178" }]);
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = {
      "/api/auth/me": { id: 1, email: "synthetic@example.com", is_active: true },
      "/api/organizations": [{ id: 1, name: "Synthetic", slug: "synthetic", role: "owner" }],
      "/api/settings/overview": {
        account: { email: "synthetic@example.com" },
        workspace: { id: 1, name: "Synthetic", slug: "synthetic", role: "owner" },
        ai: { status: "development_only", display_name: "Mock", detail: "Synthetic tests", processing_available: true },
        capabilities: { csv_import: true, historical_reports: true },
      },
    }[path];
    await route.fulfill({ status: body ? 200 : 500, json: body || { error: { message: "Unexpected API request" } } });
  });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Change Password", exact: true })).toBeVisible();
});

async function fill(page, confirmation = next) {
  await page.getByLabel("Current password", { exact: true }).fill(current);
  await page.getByLabel("New password", { exact: true }).fill(next);
  await page.getByLabel("Confirm new password", { exact: true }).fill(confirmation);
}

test("Security fields and confirmation validation block requests", async ({ page }) => {
  await expect(page.getByRole("link", { name: "Security & account" })).toBeVisible();
  for (const [label, autocomplete] of [["Current password", "current-password"], ["New password", "new-password"], ["Confirm new password", "new-password"]]) {
    const input = page.getByLabel(label, { exact: true });
    await expect(input).toHaveAttribute("type", "password");
    await expect(input).toHaveAttribute("autocomplete", autocomplete);
  }
  let requests = 0;
  page.on("request", request => { if (request.url().endsWith("/api/auth/change-password")) requests++; });
  await fill(page, "mismatch");
  await page.getByRole("button", { name: "Change Password", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Passwords do not match.");
  expect(requests).toBe(0);
  await page.getByLabel("Confirm new password", { exact: true }).fill(next);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("Submission carries CSRF, blocks duplicates, clears fields and retains Settings", async ({ page }) => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  let requests = 0;
  await page.route("**/api/auth/change-password", async route => {
    requests++;
    const request = route.request();
    expect(request.method()).toBe("POST");
    expect(request.headers()["x-csrf-token"]).toBe("synthetic-csrf");
    expect(Object.keys(request.postDataJSON()).sort()).toEqual(["current_password", "new_password"]);
    expect(new URL(request.url()).search).toBe("");
    await pending;
    await route.fulfill({ json: { message: "Password changed successfully." } });
  });
  await fill(page);
  await page.getByRole("button", { name: "Change Password", exact: true }).click();
  await expect(page.getByRole("button", { name: "Changing password…", exact: true })).toBeDisabled();
  await page.locator(".settings-password-form").evaluate(form => {
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  release();
  await expect(page.getByRole("status")).toHaveText("Password changed successfully.");
  expect(requests).toBe(1);
  for (const label of ["Current password", "New password", "Confirm new password"]) await expect(page.getByLabel(label, { exact: true })).toHaveValue("");
  await expect(page.getByRole("button", { name: "Change Password", exact: true })).toBeEnabled();
  await expect(page).toHaveURL(/\/settings$/);
  const storage = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
  expect(storage.includes(current)).toBe(false);
  expect(storage.includes(next)).toBe(false);
});

test("Incorrect current password is associated with its field; server internals stay hidden", async ({ page }) => {
  await page.route("**/api/auth/change-password", route => route.fulfill({ status: 422, json: { error: { message: "Current password is incorrect." } } }));
  await fill(page);
  await page.getByRole("button", { name: "Change Password", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Current password is incorrect.");
  await expect(page.getByLabel("Current password", { exact: true })).toHaveAttribute("aria-invalid", "true");
  await page.route("**/api/auth/change-password", route => route.fulfill({ status: 500, json: { error: { message: "private stack trace" } } }));
  await page.getByRole("button", { name: "Change Password", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("The service could not complete this request. Try again shortly.");
  await expect(page.getByText("private stack trace")).toHaveCount(0);
});
