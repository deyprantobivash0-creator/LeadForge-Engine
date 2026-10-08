import { test, expect } from './helpers/test.js';
import { login, api } from './helpers/auth.js';
import { company } from './fixtures/data.js';

// Invoked after controlled faults by the runner, rather than against fresh seed.
test('browser recovers after service restarts and shows retained intelligence after later failure', async ({ page }) => {
  await login(page);
  const lead = (await api(page, '/api/leads/search?company=E2E%20Synthetic%20Lead')).body.items[0];
  expect(lead.processing_status).toBe('failed');
  expect(lead.current_analysis).not.toBeNull();
  await page.goto('/leads');
  await page.getByLabel('Search leads', { exact: true }).fill(company);
  await page.getByLabel('Search leads', { exact: true }).press('Enter');
  await page.getByRole('button', { name: `Open ${company} details`, exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Processing: failed');
  await expect(page.getByRole('dialog')).toContainText(`AI Score: ${lead.current_analysis.lead_score}/100`);
  await page.keyboard.press('Escape');
  await page.goto(`/ai/${lead.id}`);
  await expect(page.getByRole('heading').filter({ hasText: company })).toBeVisible();
});
