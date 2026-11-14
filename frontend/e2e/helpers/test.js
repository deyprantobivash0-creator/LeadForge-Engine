import { test as base, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

export const test = base.extend({
  page: async ({ page }, providePage, testInfo) => {
    /** @type {string[]} */
    const errors = [];
    /** @param {{path:string,status:number}} failure */
    const intentional = ({ path, status }) =>
      (status === 401 && ['/api/auth/me', '/api/auth/login'].includes(path)) ||
      (status === 403 && ['/api/auth/logout', '/api/leads/'].includes(path)) ||
      (status === 404 && /^\/api\/leads\/\d+(?:\/analyses)?$/.test(path)) ||
      (status === 422 && path === '/api/imports/leads/preview');
    /** @type {{path:string,status:number}[]} */
    const httpFailures = [];
    const origin = new URL(testInfo.project.use.baseURL || 'http://127.0.0.1:8080').origin;
    if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) throw new Error('Browser QA requires a loopback HTTP origin.');
    await page.context().route('**/*', route => route.request().url().startsWith(`${origin}/`)
      ? route.continue({ headers: { ...route.request().headers(), 'X-Request-ID': `e2e-browser-${randomUUID()}` } }) : route.abort('blockedbyclient'));
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      if (message.type() === 'error' && !/^Failed to load resource: the server responded with a status of (401|403|404|409|413|422|429)/.test(message.text())) errors.push(message.text());
    });
    page.on('response', response => {
      if (response.status() >= 400) httpFailures.push({ path: new URL(response.url()).pathname, status: response.status() });
    });
    page.on('requestfailed', request => {
      if (request.failure()?.errorText !== 'net::ERR_ABORTED') errors.push(`${new URL(request.url()).pathname}: ${request.failure()?.errorText}`);
    });
    await providePage(page);
    await testInfo.attach('browser-errors', { body: JSON.stringify({ errors, httpFailures }), contentType: 'application/json' });
    /** @param {string} type @param {string} value */
    const permitted = (type, value) => testInfo.annotations.some(item => item.type === type && value.includes(`${item.description}`));
    expect(errors.filter(error => !permitted('expected-browser-error', error))).toEqual([]);
    expect(httpFailures.filter(f => !intentional(f) && !permitted('expected-http', `${f.status} ${f.path}`))).toEqual([]);
  },
});
export { expect };
