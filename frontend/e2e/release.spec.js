import { test, expect } from './helpers/test.js';
import { login, api } from './helpers/auth.js';
import { account } from './fixtures/data.js';

async function choose(page, label) {
  await page.getByRole('combobox', { name: 'Workspace', exact: true }).selectOption({ label });
}
async function upload(page, text, name = 'release.csv') {
  await page.getByLabel('Choose CSV file').setInputFiles({ name, mimeType: 'text/csv', buffer: Buffer.from(text) });
}

test('empty workspace, validation, duplicate feedback, bounded pagination and responsive release surfaces', async ({ page }) => {
  await login(page);
  await choose(page, 'E2E Empty');
  for (const [path, copy] of [['/', 'No leads in this workspace yet.'], ['/leads', 'No leads in this workspace yet.'], ['/ai', 'There are no leads in this workspace yet.'], ['/reports', 'No intelligence activity in this period.']]) {
    await page.goto(path); await expect(page.getByText(copy, { exact: true })).toBeVisible();
  }
  await page.goto('/leads');
  await page.getByRole('button', { name: 'Add Lead', exact: true }).first().click();
  await page.getByLabel('Company', { exact: true }).fill('   ');
  await page.getByLabel('Email', { exact: true }).fill('long-contact@example.com');
  await page.getByLabel('Source', { exact: true }).fill('release');
  await page.getByRole('button', { name: 'Add Lead', exact: true }).last().click();
  await expect(page.getByText('Enter a company name.')).toBeVisible();
  await expect(page.getByLabel('Company', { exact: true })).toBeFocused();
  const company = '<script>window.__releaseXss=true</script>' + 'LongCompany'.repeat(13);
  await page.getByLabel('Company', { exact: true }).fill(company);
  let createRequests = 0;
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/leads/') createRequests++; });
  await page.locator('.lead-dialog-form').evaluate(form => { form.requestSubmit(); form.requestSubmit(); });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '1 total lead', exact: true })).toBeVisible();
  expect(createRequests).toBe(1);
  test.info().annotations.push({ type: 'expected-http', description: '409 /api/leads/' });
  await page.getByRole('button', { name: 'Add Lead', exact: true }).click();
  await page.getByLabel('Company', { exact: true }).fill('Duplicate');
  await page.getByLabel('Email', { exact: true }).fill('long-contact@example.com');
  await page.getByLabel('Source', { exact: true }).fill('release');
  await page.getByRole('button', { name: 'Add Lead', exact: true }).last().click();
  await expect(page.getByRole('alert')).toHaveText('A lead with this email already exists in this workspace.');
  await page.keyboard.press('Escape');
  // Backend pagination, not a client-side slice. Tier boundaries are exact per workspace.
  let count = 1;
  for (const target of [10, 100, 500, 1000]) {
    const rows = ['company,email,source', ...Array.from({ length: target - count }, (_, i) => `Release ${count + i},release-${count + i}@example.com,release`) ].join('\n');
    const headers = { 'Content-Type': 'text/csv' };
    const preview = await api(page, '/api/imports/leads/preview', { method: 'POST', headers, body: rows });
    expect(preview.status).toBe(200);
    const imported = await api(page, '/api/imports/leads/confirm', { method: 'POST', headers: { ...headers, 'X-Import-Preview-Token': preview.body.token }, body: rows });
    expect(imported.body.imported).toBe(target - count); count = target;
    await page.reload(); await expect(page.getByRole('heading', { name: `${target} total leads`, exact: true })).toBeVisible();
    expect((await api(page, '/api/leads/?page=1&page_size=20')).body.items.length).toBe(Math.min(target, 20));
  }
  await choose(page, 'E2E Populated');
  await expect(page.getByRole('heading', { name: '6 total leads', exact: true })).toBeVisible();
  const populated = (await api(page, '/api/leads/')).body.items;
  expect(new Set(populated.map(item => item.status)).size).toBe(6);
  expect(populated.filter(item => item.current_analysis).map(item => item.current_analysis.priority).sort()).toEqual(['Cold', 'Hot', 'Warm']);
  const current = (await api(page, '/api/dashboard/v2/overview')).body;
  expect(current.pipeline.total_leads).toBe(6); expect(current.pipeline.analyzed_leads).toBe(3);
  await page.getByRole('combobox', { name: 'Priority', exact: true }).selectOption('Warm');
  await expect(page.getByRole('heading', { name: '1 matching lead', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open Populated Qualified details', exact: true }).filter({ visible: true })).toBeVisible();
  await choose(page, 'E2E Empty');
  await expect(page.getByRole('heading', { name: '1000 total leads', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByText('Page 2 of 50', { exact: true })).toBeVisible();
  await page.getByLabel('Source contains').fill('absent');
  await expect(page.getByText('No leads match these criteria.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters', exact: true }).first().click();
  await expect(page.getByText('Page 1 of 50', { exact: true })).toBeVisible();
  await page.getByLabel('Search leads', { exact: true }).fill('LongCompany');
  await expect(page.getByRole('heading', { name: '1 matching lead', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.__releaseXss)).toBeUndefined();
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ['/leads', '/imports', '/ai', '/reports', '/settings', '/']) {
      await page.goto(path); await page.waitForLoadState('networkidle');
      await expect(page).toHaveTitle(/LeadForge/);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(await page.getByRole('button').evaluateAll(items => items.filter(b => !b.textContent.trim() && !b.getAttribute('aria-label') && !b.getAttribute('aria-labelledby')).length)).toBe(0);
      await expect(page.getByRole('main')).toHaveCount(1);
      if (width === 390 && path === '/leads') await page.screenshot({ path: test.info().outputPath('mobile-leads.png'), fullPage: true });
    }
  }
});

test('CSV correction and preview recovery, Reports repeated preset, missing lead and controlled network recovery', async ({ page }) => {
  await login(page);
  await page.goto('/imports');
  await upload(page, ''); await expect(page.getByRole('alert')).toContainText('CSV is empty');
  await upload(page, 'hello', 'bad.txt'); await expect(page.getByRole('alert')).toContainText('Choose a .csv');
  await upload(page, 'company,email\nBad,invalid');
  await page.getByRole('button', { name: 'Preview import' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await upload(page, 'company,email,source\nRecovery,recovery-release@example.com,release');
  await page.getByRole('button', { name: 'Preview import' }).click();
  await expect(page.getByRole('heading', { name: 'Review before importing' })).toBeVisible();
  await page.getByRole('button', { name: 'Refresh preview' }).click();
  await expect(page.getByRole('button', { name: 'Import 1 lead', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Import 1 lead', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Import complete' })).toBeVisible();
  await page.goto('/reports');
  await page.getByRole('button', { name: '30 days', exact: true }).click();
  await expect(page.getByText('Historical analysis events', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Custom', exact: true }).click();
  await page.getByLabel('Start date').fill('2026-10-10'); await page.getByLabel('End date').fill('2026-10-01');
  await expect(page.getByText('Choose both dates in order, within 365 days.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
  await page.goto('/ai/not-a-lead'); await expect(page.getByRole('heading', { name: 'Lead unavailable' })).toBeVisible();
  await page.goto('/ai/2147483647'); await expect(page.getByText('Lead unavailable', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'All intelligence' }).click();
  await page.goto('/unknown-release'); await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  test.info().annotations.push({ type: 'expected-browser-error', description: '/api/settings/overview: net::ERR_FAILED' });
  test.info().annotations.push({ type: 'expected-browser-error', description: 'Failed to load resource: net::ERR_FAILED' });
  await page.route('**/api/settings/overview', route => route.abort('failed'));
  await page.goto('/settings'); await expect(page.getByRole('heading', { name: 'Settings unavailable' })).toBeVisible();
  await page.unroute('**/api/settings/overview');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Workspace overview', exact: true })).toBeVisible();
  // Every read surface recovers without a reload after a deliberate transport fault.
  for (const [path, endpoint, title, retry, healthy] of [
    ['/', '**/api/dashboard/v2/overview*', 'Dashboard unavailable', 'Retry', 'Revenue Intelligence Dashboard'],
    ['/leads', '**/api/leads/?*', 'Could not load leads.', 'Try again', 'Lead Workspace'],
    ['/ai', '**/api/leads/?*', 'Leads unavailable', 'Try again', 'Lead Intelligence Center'],
    ['/reports', '**/api/reports/v2/overview*', 'Report unavailable', 'Retry', 'Intelligence Reports'],
  ]) {
    // These annotations permit only the explicit fault; all other console/network failures still fail.
    const apiPath = path === '/' ? '/api/dashboard/v2/overview' : path === '/reports' ? '/api/reports/v2/overview' : '/api/leads/';
    test.info().annotations.push({ type: 'expected-browser-error', description: `${apiPath}: net::ERR_FAILED` });
    await page.route(endpoint, route => route.abort('failed'));
    await page.goto(path); await expect(page.getByText(title, { exact: true })).toBeVisible();
    await page.unroute(endpoint); await page.getByRole('button', { name: retry, exact: true }).click();
    await expect(page.getByRole('heading', { name: healthy, exact: true })).toBeVisible();
    await expect(page.getByRole('alert')).toHaveCount(0);
  }
  // Browser clock controls only the timer, never alters server timing/correctness.
  await page.clock.install();
  await page.route('**/api/settings/overview', async () => {});
  await page.goto('/settings'); await expect(page.getByText(/^Loading workspace settings/)).toBeVisible();
  await page.clock.fastForward(90001);
  await expect(page.getByRole('alert')).toContainText('request took too long');
  await page.unroute('**/api/settings/overview'); await page.clock.resume();
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Workspace overview', exact: true })).toBeVisible();

});

test('no-workspace guidance, stale preference, keyboard navigation and expired-session explanation', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('no-workspace@example.com');
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByText('Ask your workspace administrator', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Check workspace access' }).click();
  await expect(page.getByRole('heading', { name: 'Select a workspace' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await login(page);
  await page.evaluate(() => { for (const key of Object.keys(localStorage)) if (key.startsWith('leadforge-workspace-')) localStorage.setItem(key, '2147483647'); });
  await page.reload(); await expect(page.getByRole('heading', { name: 'Select a workspace' })).toBeVisible();
  await page.getByRole('button', { name: 'E2E Alpha owner' }).focus(); await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Leads', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Lead Workspace' })).toBeVisible();
  await expect(page.getByRole('main')).toBeFocused();
  await page.getByRole('button', { name: 'Add Lead', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(page.getByLabel('Company', { exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab'); await expect(page.getByRole('button', { name: 'Close Add Lead dialog' })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0);
  // Revoke the REAL session, retaining the page until its next protected request.
  expect((await api(page, '/api/auth/logout', { method: 'POST' })).status).toBe(200);
  test.info().annotations.push({ type: 'expected-http', description: '401 /api/settings/overview' });
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByText('Your session has ended. Sign in again to continue.')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toHaveCount(0);
});

test('global render boundary contains diagnostics and reloads into a healthy application', async ({ page }) => {
  await login(page);
  // Deterministic contract corruption is test-only: no production fault endpoint.
  test.info().annotations.push({ type: 'expected-browser-error', description: "Cannot destructure property 'pipeline'" });
  await page.route('**/api/dashboard/v2/overview*', route => route.fulfill({ status: 200, contentType: 'application/json', body: 'null' }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'We could not display this page.' })).toBeVisible();
  await expect(page.getByRole('alert')).not.toContainText('TypeError');
  await expect(page.getByText('Support reference:', { exact: false })).toBeVisible();
  await page.unroute('**/api/dashboard/v2/overview*');
  await page.getByRole('button', { name: 'Reload application' }).click();
  await expect(page.getByRole('heading', { name: 'Revenue Intelligence Dashboard' })).toBeVisible();
});
