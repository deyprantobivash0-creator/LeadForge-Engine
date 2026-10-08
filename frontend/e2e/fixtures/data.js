// Disposable local fixtures only. No customer or production credentials.
export const account = { email: 'e2e@example.com', password: 'local synthetic E2E password' };
export const company = 'E2E Synthetic Lead';
export const csv = 'company,email,source\n<script>window.__xss=true</script>,browser-import@example.com,e2e\nDuplicate,browser-import@example.com,e2e\nInvalid,not-an-email,e2e\n';
