# Step 5H-B safe startup diagnostics

October 10, 2026 (Asia/Dhaka). Starting SHA
`f3745069d54a60ef45ed6817079a63fbce2d079e`, main. Source/local verification only.
No Render operation, commit or push. Historical reports and preexisting work remain
unchanged. The supplied remote message proves an exception was caught in the
runtime operation; it does not identify the failing validator or prove a DB/schema
problem. No actual remote environment values were inspected.

## Every pre-Uvicorn candidate in the reviewed launch path

| Stage | Failure conditions |
| --- | --- |
| Arguments | More than one operation argument; unsupported operation. No mode means start. container selects strict Render configure when RENDER=true or platform hostname is nonempty; start always configures. |
| configure guards | ENVIRONMENT must equal production, AI_PROVIDER must equal mock, LEADFORGE_STAGING must equal lowercase true. A value such as True is rejected here even though Pydantic booleans accept it. LEADFORGE_ENV_FILE must be absent/empty; GEMINI_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, DEEPSEEK_API_KEY and HUBSPOT_ACCESS_TOKEN must be absent/empty. |
| database_url | Missing/malformed URL; driver outside postgres/postgresql/postgresql+psycopg; unsupported TLS mode; internal sslmode other than require; external TLS without an accessible real CA file or with sslmode other than verify-full. URL parse/render or CA-path errors are masked to fixed DATABASE_URL/TLS rejection. Missing SQLAlchemy import gets the dependency category. |
| Settings source/type validation | Missing ENVIRONMENT; unknown enum choices; invalid booleans/integers/strings; integers outside configured ranges. Explicit non-development dotenv fails before reading a file. Settings-source errors have a fixed source-load category. |
| Settings production DB | Malformed port or port outside 1–65535; unsupported driver; missing host/user/database; DATABASE_URL, AI_PROVIDER, CORS_ORIGINS not explicitly supplied; non-PostgreSQL production DB; query overriding connection identity; missing/short (<16) or named weak password; leadforge_dev user/database; loopback/unspecified/localhost DB host. No connection, privilege check or migration occurs at this stage. |
| Settings CORS | Comma-separated string, trim/deduplicate origins, reject empty entries. Each origin must have valid DNS/IP, HTTP(S), no wildcard/userinfo/query/fragment/non-root path, no whitespace or invalid port. Production requires HTTPS and non-local host. JSON arrays, quoted strings or backend hostname without scheme are not valid CORS input. |
| Settings Host | TRUSTED_HOSTS is a comma-separated string; empty entries ignored, lowercase/trim/deduplicate exact DNS names. No URL, port, path, wildcard or JSON array syntax. RENDER_EXTERNAL_HOSTNAME, when nonempty, must be exact lowercase single-label onrender.com hostname (label 1–63 characters, no leading/trailing hyphen). URLs, uppercase, whitespace, trailing dot, userinfo, port/path/wildcard fail. It is merged with explicit hosts and never sourced from a request. |
| Settings cookies/security | Secure must be true in production; SameSite lax or strict; session TTL >=60; cookie/header names valid nonempty HTTP tokens; Secure-prefixed cookie names require Secure; session and CSRF cookie names differ; DEBUG or disabled rate limiter forbidden in production. |
| Settings provider | Staging flag requires production+mock. Gemini requires key/model; Ollama requires valid explicit non-local host/model in production. These branches cannot be reached with a valid Render mock guard; changing provider fails earlier. Mock path constructs no paid provider. |
| server_command | PORT absent -> 8000; otherwise ASCII digits 1–5 characters and integer 1024–65535. Empty, nonnumeric, whitespace, low/high port or injected text fails before exec. |
| Imports / exec | Required runtime dependencies/imports can fail; exec may raise OSError (missing/inaccessible interpreter/resources). Fixed categories omit dependency paths, command arguments and OS exception details. |

Standard interpreter/stdlib imports at module load precede run_cli; catastrophic
interpreter or syntax failure is outside that catch. The incident's exact catch-all
message establishes that the supplied failure was inside the operation. App/engine
initialization after successful exec is a separate Uvicorn phase. migrate and seed
are separate operator modes, never prerequisites of start/container. Their TLS,
seed-confirmation/password, subprocess, readiness and operation failures also get
safe categories at the adapter boundary. Existing operator subprocess output is not
redesigned here.

## Canonical environment reproduction

Before source changes, both configure and server_command passed locally with the
user's listed production/mock/staging/TLS/cookie/log/CORS/Host/PORT/RENDER values and
a synthetic PostgreSQL URL containing a compliant encoded identity. No sockets,
real database, actual credentials or provider calls were used. Tests now exercise
start and container, postgres/postgresql/postgresql+psycopg aliases, and check
0.0.0.0:10000 selection, require TLS, exact deduplicated Host, frontend-only CORS,
and Secure cookies in fresh child processes.

**Exact failing field for the listed valid set: none reproduced.** The abbreviated
DATABASE_URL in the request does not establish the actual remote password, query,
driver/host/database or omitted/extra settings. Reproduced negative controls identify
CORS_ORIGINS and TRUSTED_HOSTS for JSON-array formats, RENDER_EXTERNAL_HOSTNAME for
URL format, DATABASE_URL/TLS for conflicting sslmode, SESSION_COOKIE_SECURE for
false/unparseable values, and PORT for invalid values. These are diagnostic cases,
not claims about remote values.

## Change and safety

backend/core/config_diagnostics.py holds an exact allowlist of owned validator text
and fixed descriptions for typed Pydantic errors. It discards input, ctx, URLs,
arbitrary location names and unknown messages; limits output to eight issues;
keeps only canonical known field names. ConfigurationError remains a RuntimeError
subclass for caller compatibility, carrying a sanitized diagnostic.

backend/core/config.py uses that typed error in load_settings; accepted/rejected
configuration is unchanged. deploy/render/runtime.py splits the existing guards
into equally strict field-specific failures, adds the safe formatter and testable
run_cli, exits 1 on rejection and prints no traceback. Only exact owned ValueError
messages are rendered; arbitrary RuntimeError text (even a forged safe-looking
prefix), OS errors, import paths and subprocess commands/output are never rendered.

Examples from synthetic negative controls:

```text
Render startup rejected: ValueError: PORT must be an unprivileged TCP port
Render startup rejected: configuration validation failed: configuration: TRUSTED_HOSTS requires exact DNS hostnames, without wildcards, ports or URLs
Render startup rejected: configuration validation failed: SESSION_COOKIE_SECURE: expected a boolean
```

No security relaxation or schema change is justified by this reproduction. A code
change is required to expose safe diagnostics; a functional validator fix remains
unproven until a safe remote failure identifies the input/category.

## Verification and changed files

Focused suite: **135 passed** across Render startup/Host/port and canonical
production/database configuration. Tests forbid sockets and actual exec, assert
exit status and output for valid/rejected configuration, and insert private markers
into DB user/password/host, keys, unused env, malformed origins/hosts, Pydantic
locations/input/context/messages and unknown exception/command details. No marker,
DB URL, traceback or environment dump is emitted.

Full backend suite: **356 passed, zero skips**, 2172 existing deprecation warnings;
pip check PASS. After adding three direct script-entrypoint tests, the complete
startup diagnostic suite passed **51 tests** (48 were included in the full backend
run). No application source changed after that full run. Gitleaks source scan + negative control and diff/source
hygiene passed. No PostgreSQL/Compose runtime smoke was rerun: diagnostics affect
pre-exec error handling, not DB queries/schema or accepted configuration; the local
Docker engine is stopped. The tests reproduce actual rejection through the script
entrypoint and successful configuration with exec replaced, as intended.

Exact changed files: backend/core/config.py; new backend/core/config_diagnostics.py;
deploy/render/runtime.py; new tests/test_render_startup_diagnostics.py;
docs/RENDER_STAGING.md; this new report. Dockerfile already copies backend/ and needs
no change. No frontend/dependency/route/repository/migration changes.

leadforge.db baseline SHA256 is
`217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`.
Original modified docs/STEP_5F_VERIFICATION.md and untracked remote/historical
Step 5H-B reports and root package manifests are preserved, excluded and uncommitted.
Final hash comparison PASS for all five preexisting files and leadforge.db;
HEAD still matches the starting SHA, index empty. No private .env contents read. Proposed commit:
`fix(deploy): report safe Render startup diagnostics`.
