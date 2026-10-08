import { test, expect } from './helpers/test.js';
import { login, api } from './helpers/auth.js';
import { company } from './fixtures/data.js';

test('production routes, workspace retention, semantics, readonly settings and responsive navigation', async ({ page }) => {
  await login(page);
  const lead = (await api(page, '/api/leads/search?company=E2E%20Synthetic%20Lead')).body.items[0];
  for (const [path, heading] of [['/', 'Revenue Intelligence Dashboard'], ['/leads', 'Lead Workspace'], ['/imports', 'Bring your leads into focus.'], ['/ai', 'Lead Intelligence Center'], ['/reports', 'Intelligence Reports'], ['/settings', 'Settings & Integrations']]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
  }
  const dashboard = (await api(page, '/api/dashboard/v2/overview')).body;
  const report = (await api(page, '/api/reports/v2/overview?preset=today')).body;
  expect(dashboard.pipeline.analyzed_leads).toBe(1);
  expect(report.summary.analysis_events).toBe(2);
  expect(report.summary.unique_analyzed_leads).toBe(1);
  expect((await api(page, `/api/leads/${lead.id}/intelligence`)).body.analysis.lead_score).toBe(30);
  await page.getByRole('combobox', { name: 'Workspace', exact: true }).selectOption({ label: 'E2E Beta' });
  expect((await api(page, '/api/leads/')).body.items[0].company).toBe('Tenant Beta Sentinel');
  expect((await api(page, `/api/leads/${lead.id}`)).status).toBe(404);
  await page.getByRole('combobox', { name: 'Workspace', exact: true }).selectOption({ label: 'E2E Alpha' });
  await page.goto('/reports');
  await page.getByRole('button', { name: 'Today', exact: true }).click();
  await expect(page.getByRole('img', { name: /2 analysis events/ })).toBeVisible();
  const downloadReady = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV', exact: true }).click();
  const download = await downloadReady;
  expect(await download.failure()).toBeNull();
  await page.goto(`/ai/${lead.id}`);
  await expect(page.getByRole('heading').filter({ hasText: company })).toBeVisible();
  await page.goto('/settings');
  expect((await api(page, '/api/settings/overview')).body.ai.provider).toBe('mock');
  await expect(page.locator('input, textarea')).toHaveCount(0);
  for (const [width, height] of [[1440, 900], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.goto('/leads');
    await expect(page.getByRole('heading', { name: 'Lead Workspace' })).toBeVisible();
    const unnamed = await page.getByRole('button').evaluateAll(buttons => buttons.filter(b => !b.textContent.trim() && !b.getAttribute('aria-label') && !b.getAttribute('aria-labelledby')).length);
    expect(unnamed).toBe(0);
    await page.getByLabel('Search leads', { exact: true }).fill(company);
    await page.getByLabel('Search leads', { exact: true }).press('Enter');
    await page.getByRole('button', { name: `Open ${company} details`, exact: true }).filter({ visible: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
  }
});

test('mock analysis processing indicator and persisted lifecycle/intelligence', async ({ page }) => {
  await login(page);
  await page.goto('/leads');
  await page.getByRole('button', { name: `Open ${company} details`, exact: true }).click();
  await page.getByLabel('Status', { exact: true }).selectOption('Qualified');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Lead lifecycle updated.', { exact: true })).toBeVisible();
  // Delay only delivery of the real server response, so the UI busy state is observable.
  await page.route('**/api/leads/*/process', async route => {
    const response = await route.fetch();
    await new Promise(resolve => setTimeout(resolve, 300));
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: 'Re-analyze Lead' }).click();
  await expect(page.getByRole('button', { name: 'Processing...' })).toBeVisible();
  await expect(page.getByText('Lead intelligence updated.', { exact: true })).toBeVisible();
  const lead = (await api(page, '/api/leads/search?company=E2E%20Synthetic%20Lead')).body.items[0];
  const detail = (await api(page, `/api/leads/${lead.id}`)).body;
  expect(detail.status).toBe('Qualified');
  expect(detail.processing_status).toBe('completed');
  expect(detail.current_analysis.priority).toBe('Cold');
  expect(detail.current_analysis.lead_score).toBeGreaterThanOrEqual(0);
});
