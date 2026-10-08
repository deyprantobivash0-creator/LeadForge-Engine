import { test, expect } from '@playwright/test';
import { leadFields, apiFieldErrors, validReportRange } from '../src/utils/validation.js';

test('validation helpers reject blank fields, impossible dates and overlong report windows without exposing input', () => {
  expect(leadFields({ company: ' ', email: 'bad', source: ' ' })).toEqual({ company: 'Enter a company name.', email: 'Enter a valid contact email.', source: 'Enter where this lead came from.' });
  expect(leadFields({ company: 'Valid', email: ' person@example.com ', source: 'web' })).toEqual({});
  expect(apiFieldErrors({ details: [{ loc: ['body', 'email'], input: 'private', msg: 'internal validator' }] })).toEqual({ email: 'Check the contact email value and try again.' });
  for (const pair of [['', ''], ['2026-02-30', '2026-03-01'], ['2026-10-02', '2026-10-01'], ['2026-01-01', '2027-01-01'], ['bad', '2026-01-01']]) expect(validReportRange(...pair)).toBe(false);
  expect(validReportRange('2026-10-01', '2026-10-01')).toBe(true);
  expect(validReportRange('2024-02-29', '2024-03-01')).toBe(true);
});
