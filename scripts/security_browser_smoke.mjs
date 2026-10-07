// Run only in the disposable Playwright container on the local edge network.
import assert from 'node:assert/strict';
import { chromium } from '/tmp/leadforge-browser/node_modules/playwright/index.mjs';
const browser = await chromium.launch({args: [`--host-resolver-rules=MAP localhost ${process.env.LF_FRONTEND_IP}`]});
try {
  const context = await browser.newContext({acceptDownloads: true});
  const page = await context.newPage();
  const errors = [], violations = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => {
    if (request.failure()?.errorText !== 'net::ERR_ABORTED') errors.push(request.failure()?.errorText);
  });
  page.on('console', message => {
    if (/content security policy|refused to|cors policy/i.test(message.text())) violations.push(message.text());
  });
  await page.goto('http://localhost:8080');
  await page.getByLabel('Email', {exact: true}).fill('runtime-smoke@example.com');
  await page.getByLabel('Password', {exact: true}).fill('container fixture password');
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await page.getByRole('heading', {name: 'Select a workspace'}).waitFor();
  await page.getByRole('button', {name: 'Runtime Synthetic 1 owner', exact: true}).click();
  for (const [path, heading] of [['/', 'Revenue Intelligence Dashboard'], ['/leads', 'Lead Workspace'],
    ['/imports', 'Bring your leads into focus.'], ['/ai', 'Lead Intelligence Center'],
    ['/ai/1', 'Runtime Synthetic'],
    ['/reports', 'Intelligence Reports'], ['/settings', 'Settings & Integrations']]) {
    await page.goto(`http://localhost:8080${path}`);
    await page.getByRole('heading', {name: heading, exact: true}).waitFor();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.getByRole('alert').count(), 0, path);
  }
  const cookies = await context.cookies();
  const session = cookies.find(c => c.name === 'leadforge_session');
  assert(session.httpOnly && !session.secure && session.sameSite === 'Lax' && session.path === '/');
  const storage = await page.evaluate(() => ({local: Object.keys(localStorage), session: Object.keys(sessionStorage)}));
  assert(storage.local.every(key => key.startsWith('leadforge-workspace-')) && storage.session.length === 0);
  await page.goto('http://localhost:8080/imports');
  await page.getByRole('heading', {name: 'Bring your leads into focus.'}).waitFor();
  await page.locator('input[type=file]').setInputFiles({name: 'security-synthetic.csv', mimeType: 'text/csv',
    buffer: Buffer.from('company,email,source\n<script>alert("synthetic")</script>,browser-security@example.com,fixture\n')});
  await page.getByRole('button', {name: 'Preview import'}).click();
  await page.getByRole('heading', {name: 'Row preview'}).waitFor();
  assert.equal(await page.locator('script').filter({hasText: 'synthetic'}).count(), 0);
  assert.equal(await page.getByText('<script>alert("synthetic")</script>', {exact: true}).count(), 1);
  await page.goto('http://localhost:8080/reports');
  await page.getByRole('heading', {name: 'Intelligence Reports'}).waitFor();
  const downloadReady = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Export CSV', exact: true}).click();
  const download = await downloadReady;
  assert(download.suggestedFilename().endsWith('.csv') && await download.failure() === null);
  const stream = await download.createReadStream();
  let csv = '';
  for await (const chunk of stream) csv += chunk.toString();
  assert(csv.startsWith('analysis_id,lead_id,company,email,score,priority,analyzed_at'));
  await page.reload();
  await page.getByRole('heading', {name: 'Intelligence Reports'}).waitFor();
  await page.getByRole('button', {name: 'Sign out', exact: true}).click();
  await page.getByRole('heading', {name: 'Sign in', exact: true}).waitFor();
  assert.equal(errors.length, 0, JSON.stringify(errors));
  assert.equal(violations.length, 0, JSON.stringify(violations));
  console.log('PASS seven product routes, login/workspace/reload/logout, escaped CSV preview and report CSV download');
  console.log('PASS cookie/storage policy; zero page errors and blocking CSP/CORS violations');
} finally { await browser.close(); }
