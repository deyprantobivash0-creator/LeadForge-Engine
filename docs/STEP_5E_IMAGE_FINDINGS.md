# Step 5E image vulnerability inventory

Docker Scout 1.25.0, local:// images, SARIF; scanned 2026-10-06. No image push or repository upload. Scanner metadata is not proof of exploitability or a clean bill of health. All original severities are retained. Counts below are package/CVE records; Node baseline includes duplicate CVEs across bundled tar versions.

| Artifact | Before records / unique CVEs | Final records / unique CVEs | Final severity counts |
| --- | --- | --- | --- |
| Backend | 89 / 89 | 69 / 69 | HIGH=9, LOW=46, MEDIUM=12, UNSPECIFIED=2 |
| Frontend | 145 / 145 | 2 / 2 | MEDIUM=1, UNSPECIFIED=1 |
| PostgreSQL | 105 / 105 | 105 / 105 | CRITICAL=2, HIGH=26, LOW=50, MEDIUM=27 |
| Node build tools | 88 / 75 | 7 / 7 | HIGH=1, MEDIUM=6 |

## Residual high/critical applicability review

G1 applies to each listed Go finding: every location is the Gosu startup helper, which switches UID and execs PostgreSQL. It receives fixed operator arguments and account files, not tenant HTTP/TLS/certificate/mail/URL/decoder inputs. Fixed Go versions exist; current affected features are unused.

These are explicit source/configuration-based inferences for registered routes and the current mock runtime, not severity downgrades. No applicable exploitable high/critical finding was identified in that boundary. A changed exposure/provider/parser/build-cache design invalidates the corresponding classification. PostgreSQL superuser fixture credentials remain a separate deployment limitation documented in SECURITY.md.

| Artifact | CVE | Severity | Installed package | Scanner fixed version | Current disposition |
| --- | --- | --- | --- | --- | --- |
| Backend | [CVE-2026-102010](https://security-tracker.debian.org/tracker/CVE-2026-102010) | HIGH | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed | C++ priority-queue erase_if/aligned-new paths are not driven by registered bounded JSON/CSV/SQL parameters. No custom SQL/code execution; IDs are comparisons, not allocation sizes. No distro fix; reassess native/parser features and future provider paths. |
| Backend | [CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Requires privileged mount/nsenter/fstab hooks. Application UID10001, capabilities ALL dropped, no-new-privileges, no host mounts/socket, no mount/nsenter operation exposed. No distro fix. |
| Backend | [CVE-2026-82560](https://security-tracker.debian.org/tracker/CVE-2026-82560) | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u4` | not fixed | POD formatter is never called by application routes or migration entrypoint; no attacker POD input. No distro fix. |
| Backend | [CVE-2026-95619](https://security-tracker.debian.org/tracker/CVE-2026-95619) | HIGH | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed | C++ priority-queue erase_if/aligned-new paths are not driven by registered bounded JSON/CSV/SQL parameters. No custom SQL/code execution; IDs are comparisons, not allocation sizes. No distro fix; reassess native/parser features and future provider paths. |
| Backend | [CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Requires privileged mount/nsenter/fstab hooks. Application UID10001, capabilities ALL dropped, no-new-privileges, no host mounts/socket, no mount/nsenter operation exposed. No distro fix. |
| Backend | [CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Requires privileged mount/nsenter/fstab hooks. Application UID10001, capabilities ALL dropped, no-new-privileges, no host mounts/socket, no mount/nsenter operation exposed. No distro fix. |
| Backend | [CVE-2026-84782](https://security-tracker.debian.org/tracker/CVE-2026-84782) | HIGH | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed | DTLS partial-write/retransmit path unused: application HTTP/TLS APIs do not implement DTLS. No distro fix. |
| Backend | [CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091) | HIGH | `pkg:deb/debian/zlib@1:1.2.13.dfsg-1` | not fixed | Scanner keeps distro-wide unfixed flag; upstream describes non-blocking gzwrite/gzprintf in 1.3.1.2?1.3.2. Installed 1.2.13/1.3.1 predates introduction; application has no non-blocking gzip-write path. |
| Backend | [CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Requires privileged mount/nsenter/fstab hooks. Application UID10001, capabilities ALL dropped, no-new-privileges, no host mounts/socket, no mount/nsenter operation exposed. No distro fix. |
| PostgreSQL | [CVE-2026-102010](https://security-tracker.debian.org/tracker/CVE-2026-102010) | HIGH | `pkg:deb/debian/gcc-14@14.2.0-19` | not fixed | C++ priority-queue erase_if/aligned-new paths are not driven by registered bounded JSON/CSV/SQL parameters. No custom SQL/code execution; IDs are comparisons, not allocation sizes. No distro fix; reassess native/parser features and future provider paths. |
| PostgreSQL | [CVE-2025-58187](https://nvd.nist.gov/vuln/detail/CVE-2025-58187) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.9 | G1 |
| PostgreSQL | [CVE-2025-58188](https://nvd.nist.gov/vuln/detail/CVE-2025-58188) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 | G1 |
| PostgreSQL | [CVE-2025-61723](https://nvd.nist.gov/vuln/detail/CVE-2025-61723) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 | G1 |
| PostgreSQL | [CVE-2025-61725](https://nvd.nist.gov/vuln/detail/CVE-2025-61725) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 | G1 |
| PostgreSQL | [CVE-2025-61726](https://nvd.nist.gov/vuln/detail/CVE-2025-61726) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.12 | G1 |
| PostgreSQL | [CVE-2025-61729](https://nvd.nist.gov/vuln/detail/CVE-2025-61729) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.11 | G1 |
| PostgreSQL | [CVE-2026-25679](https://nvd.nist.gov/vuln/detail/CVE-2026-25679) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.8 | G1 |
| PostgreSQL | [CVE-2026-32280](https://nvd.nist.gov/vuln/detail/CVE-2026-32280) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 | G1 |
| PostgreSQL | [CVE-2026-32281](https://nvd.nist.gov/vuln/detail/CVE-2026-32281) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 | G1 |
| PostgreSQL | [CVE-2026-32283](https://nvd.nist.gov/vuln/detail/CVE-2026-32283) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 | G1 |
| PostgreSQL | [CVE-2026-33811](https://nvd.nist.gov/vuln/detail/CVE-2026-33811) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | G1 |
| PostgreSQL | [CVE-2026-33814](https://nvd.nist.gov/vuln/detail/CVE-2026-33814) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | G1 |
| PostgreSQL | [CVE-2026-33818](https://nvd.nist.gov/vuln/detail/CVE-2026-33818) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | G1 |
| PostgreSQL | [CVE-2026-39820](https://nvd.nist.gov/vuln/detail/CVE-2026-39820) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | G1 |
| PostgreSQL | [CVE-2026-39836](https://nvd.nist.gov/vuln/detail/CVE-2026-39836) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | G1 |
| PostgreSQL | [CVE-2026-42499](https://nvd.nist.gov/vuln/detail/CVE-2026-42499) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | G1 |
| PostgreSQL | [CVE-2026-42504](https://nvd.nist.gov/vuln/detail/CVE-2026-42504) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.11 | G1 |
| PostgreSQL | [CVE-2026-56853](https://nvd.nist.gov/vuln/detail/CVE-2026-56853) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | G1 |
| PostgreSQL | [CVE-2026-56859](https://nvd.nist.gov/vuln/detail/CVE-2026-56859) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | G1 |
| PostgreSQL | [CVE-2026-56862](https://nvd.nist.gov/vuln/detail/CVE-2026-56862) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | G1 |
| PostgreSQL | [CVE-2026-95619](https://security-tracker.debian.org/tracker/CVE-2026-95619) | HIGH | `pkg:deb/debian/gcc-14@14.2.0-19` | not fixed | C++ priority-queue erase_if/aligned-new paths are not driven by registered bounded JSON/CSV/SQL parameters. No custom SQL/code execution; IDs are comparisons, not allocation sizes. No distro fix; reassess native/parser features and future provider paths. |
| PostgreSQL | [CVE-2026-39822](https://nvd.nist.gov/vuln/detail/CVE-2026-39822) | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.12 | G1 |
| PostgreSQL | [CVE-2026-86140](https://security-tracker.debian.org/tracker/CVE-2026-86140) | HIGH | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed | No registered XML/DTD processing or XML SQL functions; tenant strings stay bound text/JSON. Python libxml2 SAX bindings are absent from PostgreSQL image. Upstream newer fixes exist; none in pinned distro, avoid unneeded ABI/OS major migration. |
| PostgreSQL | [CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091) | HIGH | `pkg:deb/debian/zlib@1:1.3.dfsg+really1.3.1-1` | not fixed | Scanner keeps distro-wide unfixed flag; upstream describes non-blocking gzwrite/gzprintf in 1.3.1.2?1.3.2. Installed 1.2.13/1.3.1 predates introduction; application has no non-blocking gzip-write path. |
| PostgreSQL | [CVE-2026-74860](https://security-tracker.debian.org/tracker/CVE-2026-74860) | HIGH | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed | No registered XML/DTD processing or XML SQL functions; tenant strings stay bound text/JSON. Python libxml2 SAX bindings are absent from PostgreSQL image. Upstream newer fixes exist; none in pinned distro, avoid unneeded ABI/OS major migration. |
| PostgreSQL | [CVE-2026-39821](https://nvd.nist.gov/vuln/detail/CVE-2026-39821) | CRITICAL | `pkg:golang/stdlib@1.24.6` | 1.25.13 | G1 |
| PostgreSQL | [CVE-2025-68121](https://nvd.nist.gov/vuln/detail/CVE-2025-68121) | CRITICAL | `pkg:golang/stdlib@1.24.6` | 1.24.13 | G1 |
| Node build tools | [CVE-2026-93748](https://nvd.nist.gov/vuln/detail/CVE-2026-93748) | HIGH | `pkg:npm/http-cache-semantics@4.2.0` | not fixed | HIGH retained, no fix. Only anonymous npm build cache, no shared authenticated responses/session cookies or customer max-stale requests. Node/npm absent from runtime; API no-store and no proxy_cache. Reassess private/shared authenticated build caches. |

Primary references: [Gosu source](https://github.com/tianon/gosu/blob/1.19/main.go), [zlib Debian/upstream range evidence](https://security-tracker.debian.org/tracker/CVE-2026-85091), [cache advisory](https://github.com/advisories/GHSA-ch52-4w7c-c8xp). Scout locates every PostgreSQL Go record solely in /usr/local/bin/gosu; actual version 1.19/go1.24.6, actual server PID UID999 with zero effective capabilities.

Frontend residuals: busybox MEDIUM and nghttp2 UNSPECIFIED, both scanner no-fix. Health wget reads only fixed loopback JSON; HTTP/2 is not enabled. Node residual MEDIUM records are bundled ip-address, postcss-selector-parser and busybox; no customer execution path exists. Available medium CLI refreshes remain tracked for a compatible upstream tool release. Backend/PG lower-severity records below are retained, not suppressed.

## Complete final package/CVE records

| Artifact | CVE | Severity | Package/version | Fixed version |
| --- | --- | --- | --- | --- |
| Backend | CVE-2026-53613 | UNSPECIFIED | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2026-53615 | UNSPECIFIED | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2005-2541 | LOW | `pkg:deb/debian/tar@1.34+dfsg-1.2+deb12u1` | not fixed |
| Backend | CVE-2007-5686 | LOW | `pkg:deb/debian/shadow@1:4.13+dfsg1-1+deb12u2` | not fixed |
| Backend | CVE-2010-0928 | LOW | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2010-4756 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2011-3374 | LOW | `pkg:deb/debian/apt@2.6.1` | not fixed |
| Backend | CVE-2011-3389 | LOW | `pkg:deb/debian/gnutls28@3.7.9-2+deb12u7` | not fixed |
| Backend | CVE-2011-4116 | LOW | `pkg:deb/debian/perl@5.36.0-7+deb12u4` | not fixed |
| Backend | CVE-2013-4392 | LOW | `pkg:deb/debian/systemd@252.39-1~deb12u2` | not fixed |
| Backend | CVE-2017-18018 | LOW | `pkg:deb/debian/coreutils@9.1-1` | not fixed |
| Backend | CVE-2018-20796 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2018-5709 | LOW | `pkg:deb/debian/krb5@1.20.1-2+deb12u5` | not fixed |
| Backend | CVE-2018-6829 | LOW | `pkg:deb/debian/libgcrypt20@1.10.1-3+deb12u1` | not fixed |
| Backend | CVE-2019-1010022 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2019-1010023 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2019-1010024 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2019-1010025 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2019-9192 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2021-45346 | LOW | `pkg:deb/debian/sqlite3@3.40.1-2+deb12u2` | not fixed |
| Backend | CVE-2022-0563 | LOW | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2022-27943 | LOW | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed |
| Backend | CVE-2022-3219 | LOW | `pkg:deb/debian/gnupg2@2.2.40-1.1+deb12u2` | not fixed |
| Backend | CVE-2023-31437 | LOW | `pkg:deb/debian/systemd@252.39-1~deb12u2` | not fixed |
| Backend | CVE-2023-31438 | LOW | `pkg:deb/debian/systemd@252.39-1~deb12u2` | not fixed |
| Backend | CVE-2023-31439 | LOW | `pkg:deb/debian/systemd@252.39-1~deb12u2` | not fixed |
| Backend | CVE-2023-31486 | LOW | `pkg:deb/debian/perl@5.36.0-7+deb12u4` | not fixed |
| Backend | CVE-2024-2236 | LOW | `pkg:deb/debian/libgcrypt20@1.10.1-3+deb12u1` | not fixed |
| Backend | CVE-2024-26458 | LOW | `pkg:deb/debian/krb5@1.20.1-2+deb12u5` | not fixed |
| Backend | CVE-2024-26461 | LOW | `pkg:deb/debian/krb5@1.20.1-2+deb12u5` | not fixed |
| Backend | CVE-2025-14104 | LOW | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2025-27587 | LOW | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2025-29088 | LOW | `pkg:deb/debian/sqlite3@3.40.1-2+deb12u2` | not fixed |
| Backend | CVE-2025-52099 | LOW | `pkg:deb/debian/sqlite3@3.40.1-2+deb12u2` | not fixed |
| Backend | CVE-2025-5278 | LOW | `pkg:deb/debian/coreutils@9.1-1` | not fixed |
| Backend | CVE-2025-70873 | LOW | `pkg:deb/debian/sqlite3@3.40.1-2+deb12u2` | not fixed |
| Backend | CVE-2026-102473 | LOW | `pkg:deb/debian/dash@0.5.12-2` | not fixed |
| Backend | CVE-2026-102474 | LOW | `pkg:deb/debian/dash@0.5.12-2` | not fixed |
| Backend | CVE-2026-11850 | LOW | `pkg:deb/debian/krb5@1.20.1-2+deb12u5` | not fixed |
| Backend | CVE-2026-53910 | LOW | `pkg:deb/debian/diffutils@1:3.8-4` | not fixed |
| Backend | CVE-2026-56391 | LOW | `pkg:deb/debian/coreutils@9.1-1` | not fixed |
| Backend | CVE-2026-56392 | LOW | `pkg:deb/debian/coreutils@9.1-1` | not fixed |
| Backend | CVE-2026-1703 | LOW | `pkg:pypi/pip@25.0.1` | 26.0 |
| Backend | CVE-2026-105712 | LOW | `pkg:deb/debian/gnupg2@2.2.40-1.1+deb12u2` | not fixed |
| Backend | CVE-2026-95818 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2026-54872 | LOW | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2026-77696 | LOW | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2026-97399 | LOW | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2025-45582 | MEDIUM | `pkg:deb/debian/tar@1.34+dfsg-1.2+deb12u1` | not fixed |
| Backend | CVE-2026-8643 | MEDIUM | `pkg:pypi/pip@25.0.1` | 26.1.2 |
| Backend | CVE-2026-3219 | MEDIUM | `pkg:pypi/pip@25.0.1` | 26.1 |
| Backend | CVE-2026-35189 | MEDIUM | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2026-6357 | MEDIUM | `pkg:pypi/pip@25.0.1` | 26.1 |
| Backend | CVE-2026-75805 | MEDIUM | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2026-75806 | MEDIUM | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2026-13346 | MEDIUM | `pkg:pypi/pip@25.0.1` | 26.2.0 |
| Backend | CVE-2026-15534 | MEDIUM | `pkg:deb/debian/perl@5.36.0-7+deb12u4` | not fixed |
| Backend | CVE-2025-8869 | MEDIUM | `pkg:pypi/pip@25.0.1` | 25.3 |
| Backend | CVE-2026-86805 | MEDIUM | `pkg:deb/debian/glibc@2.36-9+deb12u14` | not fixed |
| Backend | CVE-2026-13595 | MEDIUM | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2026-102010 | HIGH | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed |
| Backend | CVE-2026-78409 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2026-82560 | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u4` | not fixed |
| Backend | CVE-2026-95619 | HIGH | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed |
| Backend | CVE-2026-78410 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2026-78408 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Backend | CVE-2026-84782 | HIGH | `pkg:deb/debian/openssl@3.0.22-1~deb12u1` | not fixed |
| Backend | CVE-2026-85091 | HIGH | `pkg:deb/debian/zlib@1:1.2.13.dfsg-1` | not fixed |
| Backend | CVE-2026-76642 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed |
| Frontend | CVE-2026-58055 | UNSPECIFIED | `pkg:apk/alpine/nghttp2@1.69.0-r0` | not fixed |
| Frontend | CVE-2025-60876 | MEDIUM | `pkg:apk/alpine/busybox@1.37.0-r30` | not fixed |
| PostgreSQL | CVE-2005-2541 | LOW | `pkg:deb/debian/tar@1.35+dfsg-3.1` | not fixed |
| PostgreSQL | CVE-2007-5686 | LOW | `pkg:deb/debian/shadow@1:4.17.4-2` | not fixed |
| PostgreSQL | CVE-2010-0928 | LOW | `pkg:deb/debian/openssl@3.5.7-1~deb13u3` | not fixed |
| PostgreSQL | CVE-2010-4756 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2011-3374 | LOW | `pkg:deb/debian/apt@3.0.3` | not fixed |
| PostgreSQL | CVE-2011-3389 | LOW | `pkg:deb/debian/gnutls28@3.8.9-3+deb13u4` | not fixed |
| PostgreSQL | CVE-2011-4116 | LOW | `pkg:deb/debian/perl@5.40.1-6+deb13u1` | not fixed |
| PostgreSQL | CVE-2013-4392 | LOW | `pkg:deb/debian/systemd@257.13-1~deb13u1` | not fixed |
| PostgreSQL | CVE-2015-3276 | LOW | `pkg:deb/debian/openldap@2.6.10+dfsg-1` | not fixed |
| PostgreSQL | CVE-2015-9019 | LOW | `pkg:deb/debian/libxslt@1.1.35-1.2+deb13u3` | not fixed |
| PostgreSQL | CVE-2017-14159 | LOW | `pkg:deb/debian/openldap@2.6.10+dfsg-1` | not fixed |
| PostgreSQL | CVE-2017-17740 | LOW | `pkg:deb/debian/openldap@2.6.10+dfsg-1` | not fixed |
| PostgreSQL | CVE-2017-18018 | LOW | `pkg:deb/debian/coreutils@9.7-3` | not fixed |
| PostgreSQL | CVE-2018-20796 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2018-5709 | LOW | `pkg:deb/debian/krb5@1.21.3-5+deb13u1` | not fixed |
| PostgreSQL | CVE-2018-6829 | LOW | `pkg:deb/debian/libgcrypt20@1.11.0-7+deb13u1` | not fixed |
| PostgreSQL | CVE-2019-1010022 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2019-1010023 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2019-1010024 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2019-1010025 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2019-9192 | LOW | `pkg:deb/debian/glibc@2.41-12+deb13u4` | not fixed |
| PostgreSQL | CVE-2020-15719 | LOW | `pkg:deb/debian/openldap@2.6.10+dfsg-1` | not fixed |
| PostgreSQL | CVE-2021-45346 | LOW | `pkg:deb/debian/sqlite3@3.46.1-7+deb13u2` | not fixed |
| PostgreSQL | CVE-2022-0563 | LOW | `pkg:deb/debian/util-linux@2.41.5-0+deb13u1` | not fixed |
| PostgreSQL | CVE-2022-3219 | LOW | `pkg:deb/debian/gnupg2@2.4.7-21+deb13u1` | not fixed |
| PostgreSQL | CVE-2023-31437 | LOW | `pkg:deb/debian/systemd@257.13-1~deb13u1` | not fixed |
| PostgreSQL | CVE-2023-31438 | LOW | `pkg:deb/debian/systemd@257.13-1~deb13u1` | not fixed |
| PostgreSQL | CVE-2023-31439 | LOW | `pkg:deb/debian/systemd@257.13-1~deb13u1` | not fixed |
| PostgreSQL | CVE-2024-2236 | LOW | `pkg:deb/debian/libgcrypt20@1.11.0-7+deb13u1` | not fixed |
| PostgreSQL | CVE-2024-26458 | LOW | `pkg:deb/debian/krb5@1.21.3-5+deb13u1` | not fixed |
| PostgreSQL | CVE-2024-26461 | LOW | `pkg:deb/debian/krb5@1.21.3-5+deb13u1` | not fixed |
| PostgreSQL | CVE-2025-12863 | LOW | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2025-5278 | LOW | `pkg:deb/debian/coreutils@9.7-3` | not fixed |
| PostgreSQL | CVE-2025-70873 | LOW | `pkg:deb/debian/sqlite3@3.46.1-7+deb13u2` | not fixed |
| PostgreSQL | CVE-2026-102473 | LOW | `pkg:deb/debian/dash@0.5.12-12` | not fixed |
| PostgreSQL | CVE-2026-102474 | LOW | `pkg:deb/debian/dash@0.5.12-12` | not fixed |
| PostgreSQL | CVE-2026-11850 | LOW | `pkg:deb/debian/krb5@1.21.3-5+deb13u1` | not fixed |
| PostgreSQL | CVE-2026-11979 | LOW | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-13573 | LOW | `pkg:deb/debian/llvm-toolchain-19@1:19.1.7-3` | not fixed |
| PostgreSQL | CVE-2026-13574 | LOW | `pkg:deb/debian/llvm-toolchain-19@1:19.1.7-3` | not fixed |
| PostgreSQL | CVE-2026-22185 | LOW | `pkg:deb/debian/openldap@2.6.10+dfsg-1` | not fixed |
| PostgreSQL | CVE-2026-53910 | LOW | `pkg:deb/debian/diffutils@1:3.10-4` | not fixed |
| PostgreSQL | CVE-2026-56391 | LOW | `pkg:deb/debian/coreutils@9.7-3` | not fixed |
| PostgreSQL | CVE-2026-56392 | LOW | `pkg:deb/debian/coreutils@9.7-3` | not fixed |
| PostgreSQL | CVE-2026-86137 | LOW | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-86139 | LOW | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-86141 | LOW | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-27139 | LOW | `pkg:golang/stdlib@1.24.6` | 1.25.8 |
| PostgreSQL | CVE-2026-39824 | LOW | `pkg:golang/golang.org/x/sys@0.1.0` | 0.44.0 |
| PostgreSQL | CVE-2026-105712 | LOW | `pkg:deb/debian/gnupg2@2.4.7-21+deb13u1` | not fixed |
| PostgreSQL | CVE-2025-45582 | MEDIUM | `pkg:deb/debian/tar@1.35+dfsg-3.1` | not fixed |
| PostgreSQL | CVE-2025-58183 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-47912 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-58185 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-58186 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-58189 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-61724 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-61730 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.12 |
| PostgreSQL | CVE-2026-39825 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-42505 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.12 |
| PostgreSQL | CVE-2026-42507 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.11 |
| PostgreSQL | CVE-2026-32288 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.9 |
| PostgreSQL | CVE-2026-76781 | MEDIUM | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-86144 | MEDIUM | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-56860 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2026-27142 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.8 |
| PostgreSQL | CVE-2026-32289 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.9 |
| PostgreSQL | CVE-2026-39823 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-39826 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-56858 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2026-32282 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.9 |
| PostgreSQL | CVE-2025-61727 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.11 |
| PostgreSQL | CVE-2025-61728 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.24.12 |
| PostgreSQL | CVE-2026-27145 | MEDIUM | `pkg:golang/stdlib@1.24.6` | 1.25.11 |
| PostgreSQL | CVE-2026-86138 | MEDIUM | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-86142 | MEDIUM | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-86143 | MEDIUM | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-102010 | HIGH | `pkg:deb/debian/gcc-14@14.2.0-19` | not fixed |
| PostgreSQL | CVE-2025-58187 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.9 |
| PostgreSQL | CVE-2025-58188 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-61723 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-61725 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 |
| PostgreSQL | CVE-2025-61726 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.12 |
| PostgreSQL | CVE-2025-61729 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.11 |
| PostgreSQL | CVE-2026-25679 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.8 |
| PostgreSQL | CVE-2026-32280 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 |
| PostgreSQL | CVE-2026-32281 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 |
| PostgreSQL | CVE-2026-32283 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 |
| PostgreSQL | CVE-2026-33811 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-33814 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-33818 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2026-39820 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-39836 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-42499 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 |
| PostgreSQL | CVE-2026-42504 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.11 |
| PostgreSQL | CVE-2026-56853 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2026-56859 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2026-56862 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2026-95619 | HIGH | `pkg:deb/debian/gcc-14@14.2.0-19` | not fixed |
| PostgreSQL | CVE-2026-39822 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.12 |
| PostgreSQL | CVE-2026-86140 | HIGH | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-85091 | HIGH | `pkg:deb/debian/zlib@1:1.3.dfsg+really1.3.1-1` | not fixed |
| PostgreSQL | CVE-2026-74860 | HIGH | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed |
| PostgreSQL | CVE-2026-39821 | CRITICAL | `pkg:golang/stdlib@1.24.6` | 1.25.13 |
| PostgreSQL | CVE-2025-68121 | CRITICAL | `pkg:golang/stdlib@1.24.6` | 1.24.13 |
| Node build tools | CVE-2026-104844 | MEDIUM | `pkg:npm/postcss-selector-parser@7.1.4` | 7.1.6 |
| Node build tools | CVE-2026-101911 | MEDIUM | `pkg:npm/ip-address@10.5.0` | 10.7.1 |
| Node build tools | CVE-2026-101912 | MEDIUM | `pkg:npm/ip-address@10.5.0` | 10.7.1 |
| Node build tools | CVE-2026-101913 | MEDIUM | `pkg:npm/ip-address@10.5.0` | 10.5.1 |
| Node build tools | CVE-2025-60876 | MEDIUM | `pkg:apk/alpine/busybox@1.37.0-r30` | not fixed |
| Node build tools | CVE-2026-101910 | MEDIUM | `pkg:npm/ip-address@10.5.0` | 10.5.1 |
| Node build tools | CVE-2026-93748 | HIGH | `pkg:npm/http-cache-semantics@4.2.0` | not fixed |

## Original high/critical remediation ledger

Updated OS packages (OpenSSL, Perl, PCRE2 and Alpine security revisions), replaced Nginx r1 with same-version r7, removed unused Nginx modules/Yarn/Corepack, used Node22.22.2/npm12.2 with compatible checksum-pinned brace-expansion5.0.12/undici6.28.1 patches. Python/project npm fixes are detailed in STEP_5E_VERIFICATION.md. A record absent below the final inventory may be fixed by update or removed with an unused component; this ledger distinguishes retained conditions.

| Artifact | Original CVE | Severity | Original package | Original fixed version | Final scanner disposition |
| --- | --- | --- | --- | --- | --- |
| Backend | CVE-2026-102010 | HIGH | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-78409 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-48962 | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-42497 | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-48959 | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-54874 | HIGH | `pkg:deb/debian/openssl@3.0.20-1~deb12u2` | 3.0.22-1~deb12u1 | No longer detected after update/component removal |
| Backend | CVE-2026-63072 | HIGH | `pkg:deb/debian/openssl@3.0.20-1~deb12u2` | 3.0.22-1~deb12u1 | No longer detected after update/component removal |
| Backend | CVE-2026-63076 | HIGH | `pkg:deb/debian/openssl@3.0.20-1~deb12u2` | 3.0.22-1~deb12u1 | No longer detected after update/component removal |
| Backend | CVE-2026-82560 | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-103111 | HIGH | `pkg:deb/debian/pcre2@10.42-1+deb12u1` | 10.42-1+deb12u2 | No longer detected after update/component removal |
| Backend | CVE-2026-95619 | HIGH | `pkg:deb/debian/gcc-12@12.2.0-14+deb12u1` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-78410 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-78408 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-84782 | HIGH | `pkg:deb/debian/openssl@3.0.20-1~deb12u2` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-85091 | HIGH | `pkg:deb/debian/zlib@1:1.2.13.dfsg-1` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-57432 | HIGH | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-76642 | HIGH | `pkg:deb/debian/util-linux@2.38.1-5+deb12u3` | not fixed | Retained; applicability reviewed above |
| Backend | CVE-2026-12087 | CRITICAL | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-13221 | CRITICAL | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-42496 | CRITICAL | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Backend | CVE-2026-75803 | CRITICAL | `pkg:deb/debian/openssl@3.0.20-1~deb12u2` | 3.0.22-1~deb12u1 | No longer detected after update/component removal |
| Backend | CVE-2026-8376 | CRITICAL | `pkg:deb/debian/perl@5.36.0-7+deb12u3` | 5.36.0-7+deb12u4 | No longer detected after update/component removal |
| Frontend | CVE-2026-9080 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-13608 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-34181 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-89161 | HIGH | `pkg:apk/alpine/pcre2@10.47-r0` | 10.48-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-9547 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-11352 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-11586 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-12064 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-14456 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-14457 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-18798 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-27135 | HIGH | `pkg:apk/alpine/nghttp2@1.68.0-r0` | 1.68.1 | No longer detected after update/component removal |
| Frontend | CVE-2026-28388 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-28389 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-28390 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-31790 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-33416 | HIGH | `pkg:apk/alpine/libpng@1.6.55-r0` | 1.6.56-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-33630 | HIGH | `pkg:apk/alpine/c-ares@1.34.6-r0` | 1.34.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-34180 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-34183 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-3805 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.19.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-42764 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-45445 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-49975 | HIGH | `pkg:apk/alpine/nginx@1.28.3-r1` | 1.28.3-r3 | No longer detected after update/component removal |
| Frontend | CVE-2026-54874 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-5773 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.20.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-6276 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.20.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-63072 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-63075 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-63076 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-80229 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-80230 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-80231 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-80255 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-82208 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-8932 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-9076 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-9545 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-9546 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-103111 | HIGH | `pkg:apk/alpine/pcre2@10.47-r0` | 10.49-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-33636 | HIGH | `pkg:apk/alpine/libpng@1.6.55-r0` | 1.6.56-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-78410 | HIGH | `pkg:apk/alpine/util-linux@2.41.2-r0` | 2.41.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-78408 | HIGH | `pkg:apk/alpine/util-linux@2.41.2-r0` | 2.41.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-86140 | HIGH | `pkg:apk/alpine/libxml2@2.13.9-r0` | not fixed | No longer detected after update/component removal |
| Frontend | CVE-2026-28387 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-40200 | HIGH | `pkg:apk/alpine/musl@1.2.5-r21` | 1.2.5-r23 | No longer detected after update/component removal |
| Frontend | CVE-2026-7383 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-8286 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-82209 | HIGH | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-86145 | HIGH | `pkg:apk/alpine/pcre2@10.47-r0` | 10.48-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-56434 | HIGH | `pkg:apk/alpine/nginx@1.28.3-r1` | 1.28.3-r6 | No longer detected after update/component removal |
| Frontend | CVE-2026-76642 | HIGH | `pkg:apk/alpine/util-linux@2.41.2-r0` | 2.41.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-66046 | HIGH | `pkg:apk/alpine/expat@2.7.5-r0` | 2.8.4-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-76641 | HIGH | `pkg:apk/alpine/expat@2.7.5-r0` | 2.8.4-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-93990 | HIGH | `pkg:apk/alpine/expat@2.7.5-r0` | 2.8.5-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-45447 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-60005 | HIGH | `pkg:apk/alpine/nginx@1.28.3-r1` | 1.28.3-r6 | No longer detected after update/component removal |
| Frontend | CVE-2026-11564 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-18924 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-34182 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-75803 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-8924 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-8926 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-8927 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-42055 | CRITICAL | `pkg:apk/alpine/nginx@1.28.3-r1` | 1.28.3-r4 | No longer detected after update/component removal |
| Frontend | CVE-2026-42533 | CRITICAL | `pkg:apk/alpine/nginx@1.28.3-r1` | 1.28.3-r6 | No longer detected after update/component removal |
| Frontend | CVE-2026-9256 | CRITICAL | `pkg:apk/alpine/nginx@1.28.3-r1` | 1.28.3-r2 | No longer detected after update/component removal |
| Frontend | CVE-2026-10536 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-11856 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-19931 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-31789 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-63073 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-8925 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| Frontend | CVE-2026-9079 | CRITICAL | `pkg:apk/alpine/curl@8.17.0-r1` | 8.22.0-r0 | No longer detected after update/component removal |
| PostgreSQL | CVE-2026-102010 | HIGH | `pkg:deb/debian/gcc-14@14.2.0-19` | not fixed | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-58187 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.9 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-58188 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-61723 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-61725 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.8 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-61726 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.12 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-61729 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.24.11 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-25679 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.8 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-32280 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-32281 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-32283 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.9 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-33811 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-33814 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-33818 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-39820 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-39836 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-42499 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.10 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-42504 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.11 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-56853 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-56859 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-56862 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.13 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-95619 | HIGH | `pkg:deb/debian/gcc-14@14.2.0-19` | not fixed | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-39822 | HIGH | `pkg:golang/stdlib@1.24.6` | 1.25.12 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-86140 | HIGH | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-85091 | HIGH | `pkg:deb/debian/zlib@1:1.3.dfsg+really1.3.1-1` | not fixed | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-74860 | HIGH | `pkg:deb/debian/libxml2@2.12.7+dfsg+really2.9.14-2.1+deb13u3` | not fixed | Retained; applicability reviewed above |
| PostgreSQL | CVE-2026-39821 | CRITICAL | `pkg:golang/stdlib@1.24.6` | 1.25.13 | Retained; applicability reviewed above |
| PostgreSQL | CVE-2025-68121 | CRITICAL | `pkg:golang/stdlib@1.24.6` | 1.24.13 | Retained; applicability reviewed above |
| Node build tools | CVE-2026-26960 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.8 | No longer detected after update/component removal |
| Node build tools | CVE-2026-26960 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.8 | No longer detected after update/component removal |
| Node build tools | CVE-2026-34181 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2025-64756 | HIGH | `pkg:npm/glob@10.4.5` | 11.1.0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-102276 | HIGH | `pkg:npm/brace-expansion@2.0.2` | 2.1.5 | No longer detected after update/component removal |
| Node build tools | CVE-2026-102278 | HIGH | `pkg:npm/brace-expansion@2.0.2` | 2.1.6 | No longer detected after update/component removal |
| Node build tools | CVE-2026-14257 | HIGH | `pkg:npm/brace-expansion@2.0.2` | 5.0.8 | No longer detected after update/component removal |
| Node build tools | CVE-2026-14456 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-14457 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-18798 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-27903 | HIGH | `pkg:npm/minimatch@9.0.5` | 9.0.7 | No longer detected after update/component removal |
| Node build tools | CVE-2026-27904 | HIGH | `pkg:npm/minimatch@9.0.5` | 9.0.7 | No longer detected after update/component removal |
| Node build tools | CVE-2026-28388 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-28389 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-28390 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-31790 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-33671 | HIGH | `pkg:npm/picomatch@4.0.2` | 4.0.4 | No longer detected after update/component removal |
| Node build tools | CVE-2026-34180 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-34183 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-42764 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-45445 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-48815 | HIGH | `pkg:npm/sigstore@3.1.0` | 4.1.1 | No longer detected after update/component removal |
| Node build tools | CVE-2026-54874 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-63072 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-63075 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-63076 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-69152 | HIGH | `pkg:npm/brace-expansion@2.0.2` | 2.1.4 | No longer detected after update/component removal |
| Node build tools | CVE-2026-73566 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.21 | No longer detected after update/component removal |
| Node build tools | CVE-2026-73566 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.21 | No longer detected after update/component removal |
| Node build tools | CVE-2026-9076 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-13149 | HIGH | `pkg:npm/brace-expansion@2.0.2` | 2.1.2 | No longer detected after update/component removal |
| Node build tools | CVE-2026-69192 | HIGH | `pkg:npm/ip-address@9.0.5` | 10.3.1 | No longer detected after update/component removal |
| Node build tools | CVE-2026-9496 | HIGH | `pkg:npm/pacote@19.0.1` | 21.5.1 | No longer detected after update/component removal |
| Node build tools | CVE-2026-9496 | HIGH | `pkg:npm/pacote@20.0.0` | 21.5.1 | No longer detected after update/component removal |
| Node build tools | CVE-2026-28387 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-40200 | HIGH | `pkg:apk/alpine/musl@1.2.5-r21` | 1.2.5-r23 | No longer detected after update/component removal |
| Node build tools | CVE-2026-7383 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-23745 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.3 | No longer detected after update/component removal |
| Node build tools | CVE-2026-23745 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.3 | No longer detected after update/component removal |
| Node build tools | CVE-2026-24842 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.7 | No longer detected after update/component removal |
| Node build tools | CVE-2026-24842 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.7 | No longer detected after update/component removal |
| Node build tools | CVE-2026-29786 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.10 | No longer detected after update/component removal |
| Node build tools | CVE-2026-29786 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.10 | No longer detected after update/component removal |
| Node build tools | CVE-2026-31802 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.11 | No longer detected after update/component removal |
| Node build tools | CVE-2026-31802 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.11 | No longer detected after update/component removal |
| Node build tools | CVE-2026-26996 | HIGH | `pkg:npm/minimatch@9.0.5` | 10.2.1 | No longer detected after update/component removal |
| Node build tools | CVE-2026-59874 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.18 | No longer detected after update/component removal |
| Node build tools | CVE-2026-59874 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.18 | No longer detected after update/component removal |
| Node build tools | CVE-2026-93748 | HIGH | `pkg:npm/http-cache-semantics@4.2.0` | not fixed | Retained; applicability reviewed above |
| Node build tools | CVE-2026-23950 | HIGH | `pkg:npm/tar@7.4.3` | 7.5.4 | No longer detected after update/component removal |
| Node build tools | CVE-2026-23950 | HIGH | `pkg:npm/tar@6.2.1` | 7.5.4 | No longer detected after update/component removal |
| Node build tools | CVE-2026-45447 | HIGH | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-34182 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.7-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-75803 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-59873 | CRITICAL | `pkg:npm/tar@6.2.1` | 7.5.19 | No longer detected after update/component removal |
| Node build tools | CVE-2026-59873 | CRITICAL | `pkg:npm/tar@7.4.3` | 7.5.19 | No longer detected after update/component removal |
| Node build tools | CVE-2026-31789 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.6-r0 | No longer detected after update/component removal |
| Node build tools | CVE-2026-63073 | CRITICAL | `pkg:apk/alpine/openssl@3.5.5-r0` | 3.5.8-r0 | No longer detected after update/component removal |
