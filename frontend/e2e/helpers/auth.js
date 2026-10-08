import { expect } from '@playwright/test';
import { account } from '../fixtures/data.js';

export async function login(page) {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill(account.email);
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('heading', { name: 'Select a workspace' }).waitFor();
  await page.getByRole('button', { name: 'E2E Alpha owner', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Revenue Intelligence Dashboard' })).toBeVisible();
}

export async function api(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => {
    const csrf = document.cookie.split('; ').find(c => c.startsWith('leadforge_csrf='))?.split('=')[1];
    const org = Object.entries(localStorage).find(([key]) => key.startsWith('leadforge-workspace-'))?.[1];
    const response = await fetch(path, { credentials: 'include', ...options,
      headers: { 'X-Organization-ID': org, 'X-CSRF-Token': csrf, ...options.headers } });
    return { status: response.status, body: await response.json() };
  }, { path, options });
}
