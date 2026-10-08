// Synthetic-only browser regression against the local Kubernetes ingress.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from '/tmp/leadforge-browser/node_modules/playwright/index.mjs';
const origin = 'https://staging.leadforge.test';
const fixture = JSON.parse(await fs.readFile('/evidence/fixture.json', 'utf8'));
assert.equal(fixture.synthetic, true);
const password = (await fs.readFile('/qa/password', 'utf8')).trim();
const browser = await chromium.launch({args: [
  '--disable-background-networking',
  `--host-resolver-rules=MAP staging.leadforge.test:443 ${process.env.LF_INGRESS_IP}:8443`,
  `--ignore-certificate-errors-spki-list=${process.env.LF_LOCAL_CERT_SPKI}`,
]});
try {
  const context = await browser.newContext({acceptDownloads: true});
  await context.route('**/*', route => route.request().url().startsWith(origin + '/') ? route.continue() : route.abort());
  const page = await context.newPage();
  const errors = [], violations = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => {
    if (request.failure()?.errorText !== 'net::ERR_ABORTED') errors.push(request.failure()?.errorText);
  });
  page.on('console', message => {
    if (/content security policy|refused to|cors policy/i.test(message.text())) violations.push(message.text());
  });
  await page.goto(origin);
  await page.getByLabel('Email', {exact: true}).fill(fixture.fixtures[0].email);
  await page.getByLabel('Password', {exact: true}).fill(password);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await page.getByRole('heading', {name: 'Select a workspace'}).waitFor();
  await page.getByRole('button', {name: 'STAGING SYNTHETIC alpha owner', exact: true}).click();
  for (const [path, heading] of [['/', 'Revenue Intelligence Dashboard'], ['/leads', 'Lead Workspace'],
    ['/imports', 'Bring your leads into focus.'], ['/ai', 'Lead Intelligence Center'],
    ['/reports', 'Intelligence Reports'], ['/settings', 'Settings & Integrations']]) {
    await page.goto(origin + path);
    await page.getByRole('heading', {name: heading, exact: true}).waitFor();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.getByRole('alert').count(), 0, path);
    await page.screenshot({path: `/evidence/browser-${path.slice(1) || 'dashboard'}.png`, fullPage: true});
  }
  await page.goto(origin + '/ai/' + fixture.fixtures[0].lead_ids[0]);
  await page.waitForLoadState('networkidle');
  assert.equal(await page.getByRole('alert').count(), 0);
  assert(await page.getByRole('heading').filter({hasText: 'SYNTHETIC'}).count() > 0);
  const cookies = await context.cookies();
  const session = cookies.find(c => c.name === 'leadforge_session');
  assert(session.httpOnly && session.secure && session.sameSite === 'Lax' && session.path === '/');
  const storage = await page.evaluate(() => ({local: Object.keys(localStorage), session: Object.keys(sessionStorage)}));
  assert(storage.local.every(key => key.startsWith('leadforge-workspace-')) && storage.session.length === 0);
  await page.goto(origin + '/imports');
  await page.getByRole('heading', {name: 'Bring your leads into focus.'}).waitFor();
  await page.locator('input[type=file]').setInputFiles({name: 'kubernetes-synthetic.csv', mimeType: 'text/csv',
    buffer: Buffer.from(`company,email,source\n<script>alert("synthetic")</script>,kube-browser-${Date.now()}@example.com,fixture\n`)});
  await page.getByRole('button', {name: 'Preview import'}).click();
  await page.getByRole('heading', {name: 'Row preview'}).waitFor();
  assert.equal(await page.locator('script').filter({hasText: 'synthetic'}).count(), 0);
  assert.equal(await page.getByText('<script>alert("synthetic")</script>', {exact: true}).count(), 1);
  await page.goto(origin + '/reports');
  await page.getByRole('heading', {name: 'Intelligence Reports'}).waitFor();
  const downloadReady = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Export CSV', exact: true}).click();
  const download = await downloadReady;
  assert(download.suggestedFilename().endsWith('.csv') && await download.failure() === null);
  const stream = await download.createReadStream();
  let csv = '';
  for await (const chunk of stream) csv += chunk.toString();
  assert(csv.startsWith('analysis_id,lead_id,company,email,score,priority,analyzed_at'));
  assert(!csv.includes('staging-beta'));
  await page.reload();
  await page.getByRole('heading', {name: 'Intelligence Reports'}).waitFor();
  await page.getByRole('button', {name: 'Sign out', exact: true}).click();
  await page.getByRole('heading', {name: 'Sign in', exact: true}).waitFor();
  assert.equal(errors.length, 0, JSON.stringify(errors));
  assert.equal(violations.length, 0, JSON.stringify(violations));
  await fs.writeFile('/evidence/browser-verification.json', JSON.stringify({status: 'PASS',
    scope: 'local synthetic TLS certificate SPKI exception only',
    checks: 'seven product routes, login, explicit workspace, reload, secure cookies/storage, escaped CSV preview, tenant-scoped report CSV download, logout',
    page_errors: errors.length, csp_cors_violations: violations.length}, null, 2) + '\n');
  console.log('PASS browser product routes, auth/workspace/reload/logout, secure cookies/storage, CSV and zero errors/CSP/CORS violations');
} finally { await browser.close(); }
