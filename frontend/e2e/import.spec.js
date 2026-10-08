import { test, expect } from './helpers/test.js';
import { login, api } from './helpers/auth.js';
import { csv } from './fixtures/data.js';

test('CSV preview is nonmutating, partial confirm skips duplicate/invalid, XSS is escaped', async ({ page }) => {
  await login(page);
  const before = (await api(page, '/api/leads/')).body.total;
  await page.goto('/imports');
  await page.getByLabel('Choose CSV file').setInputFiles({ name: 'synthetic.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await page.getByRole('button', { name: 'Preview import' }).click();
  await expect(page.getByRole('heading', { name: 'Row preview' })).toBeVisible();
  expect((await api(page, '/api/leads/')).body.total).toBe(before);
  await expect(page.getByText('<script>window.__xss=true</script>', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
  await page.getByRole('button', { name: 'Import 1 lead', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Import complete' })).toBeVisible();
  expect((await api(page, '/api/leads/')).body.total).toBe(before + 1);
  const imported = (await api(page, '/api/leads/search?email=browser-import')).body.items[0];
  expect(imported.processing_status).toBe('pending');
  expect(imported.current_analysis).toBeNull();
  await page.getByRole('button', { name: 'Import another file' }).click();
  await page.getByLabel('Choose CSV file').setInputFiles({ name: 'duplicate.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await page.getByRole('button', { name: 'Preview import' }).click();
  await expect(page.getByRole('button', { name: 'Import 0 leads' })).toBeDisabled();
  await page.getByRole('button', { name: 'Choose another file' }).click();
  await page.getByLabel('Choose CSV file').setInputFiles({ name: 'empty.csv', mimeType: 'text/csv', buffer: Buffer.from('company,email,source\n') });
  await page.getByRole('button', { name: 'Preview import' }).click();
  await expect(page.getByRole('alert')).toContainText('no data rows');
});
