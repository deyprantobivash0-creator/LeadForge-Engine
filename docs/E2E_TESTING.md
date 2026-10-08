# Local browser E2E testing

Step 5J-L uses the production-built React application behind Nginx, FastAPI and
PostgreSQL 16.15. It does not use Vite's development server. AI remains mock.
The runner creates a unique `leadforge-e2e-*` Compose project with its own
database volume and images. It combines the existing runtime and CI override;
the existing application on host port 8080 and its data remain untouched.
Chromium shares the disposable frontend's network namespace and reaches
`http://127.0.0.1:8080`. There are no published test backend or database ports.

## Prerequisites and commands

Use Python 3.12, Docker Desktop with Linux containers, Compose 2.24.4 or newer,
and sufficient free space for the pinned browser image. Docker must be on PATH.
No private `.env` file is read: Compose receives `deploy/compose.env` explicitly.
The frontend workspace pins `@playwright/test` 1.58.2 and the corresponding
official Microsoft browser image by digest. Dependency installation happens
during the tool build, without credentials and with lifecycle scripts disabled.
Browser execution installs nothing and allows requests only to the local origin.

From the repository root:

```powershell
./.venv-ci/Scripts/python.exe -B scripts/verify_e2e_local.py
```

An existing supported Python environment also works; the host runner uses the
standard library. SQLAlchemy and application dependencies run inside the built
backend image. All runtime schema creation uses the existing Alembic migration
job. `scripts/e2e_fixture.py` refuses normal runtime invocation without the
explicit disposable marker; seed also refuses a database already containing users.

The only test account is `e2e@example.com`, password
`local synthetic E2E password`, with owner memberships in E2E Alpha and Beta.
These are public synthetic fixtures for a disposable local database, not personal
or production credentials. Alpha starts with one Lead and two historical analysis
events (80 then 30); Beta has a sentinel Lead. The runner never seeds the existing
development database or `leadforge.db`.

## Test organization and coverage

`frontend/e2e/fixtures/` holds synthetic data; `helpers/auth.js` handles sign-in
and browser-origin API assertions; `helpers/test.js` collects browser errors and
classifies intentional auth, CSRF, tenant and empty-CSV responses by path/status.
Separate auth, product, import and recovery specifications cover login/logout,
revoked cookie replay, workspace selection/switching, all seven direct routes,
current versus historical analytics, mock analysis, lifecycle persistence,
nonmutating CSV preview, partial confirmation, duplicates, empty files and XSS.
The Python runner adds real database-backed failed analysis and session-expiry
faults. Provider failure is injected through the existing service constructor,
never through a production fault endpoint or a change to auth/AI architecture.
The recovery browser specification verifies that retained intelligence renders
after a later failed attempt and that the frontend works after service restarts.

The mock processing request reaches the real API. Only delivery of its response
to the browser is delayed 300 ms to observe the busy indicator reliably; the
measured API processing latency does not include this browser observation delay.

Chromium is the verified browser. Desktop 1440x900, tablet 768x1024 and mobile
390x844 cover navigation and usable Lead details. Firefox, WebKit and real mobile
devices have not been verified. Accessibility smoke covers input labels, named
buttons, navigation landmarks, keyboard Tab, dialog focus and Escape; it is not
an accessibility certification or an automated contrast audit.

For an already provisioned isolated fixture, `npm run test:e2e` in `frontend`
runs the four primary tests. Host use needs the matching local runtime and a
locally installed Chromium (`npx playwright install chromium`); browser binaries
are never committed. The full runner uses the pinned Docker browser instead.
Recovery is deliberately separate: `E2E_RECOVERY=1` plus selectors
`auth.spec.js recovery.spec.js` runs after faults. Do not run mutating specifications
against shared developer or customer data.

## Evidence, debugging and cleanup

Default evidence is ignored `.staging-artifacts/5j-l/`. `--evidence` can select
another directory under `.staging-artifacts` to retain separate runs. Reports
include `browser.json`, `browser-recovery.json`, `performance.json`, resource
samples, privacy-checked runtime logs and `verification.json`. A failure never
becomes PASS. Traces and screenshots are retained only on browser failure;
they may contain synthetic session cookies and must remain private local evidence.
No videos, HTML reports, screenshots, traces, database dumps, certificates or
browser binaries belong in the commit. Host Playwright outputs and Docker build
contexts also exclude generated test results/reports.

Inspect the named failing assertion and local trace with
`npx playwright show-trace <trace.zip>`. Do not suppress browser errors or broaden
the intentional-response list to make a broken flow pass. The initial and
recovery JSON reports remain separate. No retries hide flaky behavior.

The runner always removes only its uniquely named drivers, project containers,
networks and disposable volume, including on failure. Images remain in Docker's
local build cache. If the host process is forcibly killed, identify the project
from `verification.json`/run output and use the exact same Compose project and
file arguments for `down --volumes`; never remove another project's volume.
Preexisting local file and SQLite hashes are compared before/after.

Keep this suite local-first until multiple clean CI-equivalent runs establish
browser/download availability and acceptable runtime. A later optional dedicated
E2E job can invoke this runner on Linux. The existing mandatory six-job quality
workflow and its aggregate gate are unchanged; performance numbers should not
become mandatory cloud SLAs from this local sample.
