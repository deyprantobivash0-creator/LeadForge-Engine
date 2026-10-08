# Step 5H DigitalOcean resource-creation checkpoint

> **Current status — October 8, 2026:** Remote Step 5H is **DEFERRED — NO DROPLET CREATED**.
> Cloud billing/provider deployment was intentionally postponed; this is not a LeadForge
> application failure. **REAL REMOTE STAGING NOT YET EXECUTED.** Step 5I remains **BLOCKED**
> by remote Step 5H. Docker Desktop local Step 5H-L is tracked separately in
> [local Kubernetes verification](STEP_5H_L_VERIFICATION.md). Historical authorization
> and account-access checkpoints below are preserved; they do not authorize current
> cloud execution during this local-only rehearsal.

October 7, 2026. **CREATION AUTHORIZED - DIGITALOCEAN ACCOUNT ACCESS BLOCKED.**
User chose DigitalOcean Singapore, Basic 2 vCPU/4 GiB/~80 GiB, maximum USD 25/month
primary Droplet budget, self-hosted PostgreSQL 16.15 and SSH keys. The user subsequently provided FINAL STAGING RESOURCE CREATION AUTHORIZATION
for exactly this one Droplet. No repeat creation approval is required. Creation
now has the explicitly approved SSH public key and administrative public IP.
Execution is blocked by unavailable account-control/browser access. 5H remains READY FOR DEPLOYMENT AUTHORIZATION and
5I BLOCKED. No new commit/push, DNS change, cloud resource or source transfer.

| Required item | Selected plan |
| --- | --- |
| 1. Exact Droplet | One Basic **Regular** bundled plan, size slug `s-2vcpu-4gb`: 2 shared vCPU, 4 GiB RAM, 80 GiB SSD, 4,000 GiB included transfer. Singapore region `sgp1`. Proposed name `leadforge-staging-sgp1`. Select this exact plan, not Premium or v5. |
| 2. Listed monthly cost | USD **24.00/month** (listed USD 0.03571/hour), below the USD 25 base-resource cap. Before purchase verify the authenticated creation quote, regional capacity and applicable account taxes. Stop if the applicable approved cost exceeds the cap; do not silently substitute a larger/different plan. No account-specific quote/capacity has yet been verified. |
| 3. OS | Official **Ubuntu 24.04 LTS x64** image, slug `ubuntu-24-04-x64`, current provider image at creation. Record actual image ID and installed OS version after provisioning. Use reviewed Docker Engine/Compose installation. |
| 4. Public inbound ports | TCP 80 (ACME HTTP-01 and canonical HTTPS redirect), TCP 443 (Nginx HTTPS), TCP 22 only from authorized admin IPv4 CIDR(s). No public 5432, 8000, Docker API or other application ports. Use no-cost DigitalOcean Cloud Firewall and host/Docker filtering. IPv6 not enabled for this initial deployment. |
| 5. SSH | User-approved SSH public key added at creation; bootstrap through verified-host-key SSH, create a named sudo deployment operator, confirm key access before disabling root/password login. Never display/read private key material or disable host-key checking. Local OpenSSH ssh/scp is available; no standard local .ssh/*.pub key was discovered. Key selection and admin IP CIDR remain to be supplied/established securely. |
| 6. Temporary HTTPS hostname | `leadforge-stage-<Droplet-IPv4-with-dashes>.sslip.io`, selected only after the actual primary IPv4 exists. sslip.io resolves embedded public IPs without buying a domain or editing unrelated DNS. Obtain an individual Let's Encrypt certificate with Certbot standalone HTTP-01 on port 80, then mount its full chain/private key outside source into existing Nginx. No wildcard/shared private certificate and no extra proxy. Confirm DNS, trusted chain, hostname and renewal dry-run before final 5H success. |
| 7. Extra paid resource | **None required for this phase.** No managed DB, additional VM, load balancer, volume, Spaces, reserved IP, paid snapshot/automated Droplet backup or domain purchase. Cloud Firewall has no additional charge. Store Compose DB volume and temporary drill artifacts on included SSD; retain encrypted backup/recovery material on an already authorized local destination after deployment. Off-host paid storage would need separate approval. |

## HTTPS feasibility and failure boundary

The service's primary documentation supports DNS names containing the IP and
individual HTTP-01 certificates from Let's Encrypt. The committed staging helper
accepts the proposed hostname format. Nginx directly terminates TLS, preserving
same-origin /api, secure production cookies, host validation, CSP/security headers,
structured logging/request IDs and the existing migration/app/backup role design.
No application source change is required for this hostname strategy.

This is a feasible temporary staging strategy, not an issued certificate or owned
domain. It depends on third-party DNS availability and CA limits; certificate
issuance cannot be proven before the actual IP/host exists. Test ACME staging first,
then trusted issuance. Only the trusted production CA chain qualifies for final
5H verification. Install renewal with the reviewed controlled frontend stop/copy/
recreation procedure, and verify a renewal dry-run. Keep IPv4 for the deployment's
lifetime; releasing/reassigning the IP invalidates this temporary identity.

If proper trusted HTTPS cannot be established, stop remote completion and request
one controlled DNS subdomain such as `staging.<user-owned-domain>` with an A record
to this Droplet's primary IPv4. Do not buy a domain, weaken TLS checks or report 5H
COMPLETE. Do not keep retrying issuance into CA limits. Explain any retained paid
Droplet state and obtain a separate decision rather than silently purchasing more.

## Exact verified source and deployment gates

GitHub private main and successful Quality push run 37609652682 verify:
`6f8b1f1dbbb919078581e829357d692af18b4091`.

A local ignored archive was prepared directly by `git archive` of this SHA:
`.staging-artifacts/deployment-plan/source.tar.gz`, 365 committed source files.
Its SHA-256 is
`0fd44dab561dd3465951fd5d1e1a105cad5347b855aed2337687621374635f8c`.
Adjacent manifest.json records the commit and per-file SHA-256 hashes. No archive
was transferred. Dirty local files and root untracked manifests are excluded.
This is the approved source archive; do not reuse the historical dirty snapshot.

After final resource confirmation and secure account/key access: recheck the quote,
region/size/image; attach approved key/firewall; create exactly one Droplet; verify
host SSH identity; establish temporary hostname and trusted certificate; provision
staging-only secrets and separate admin/migrator/app/backup identities; build and
run exact-source Compose; perform all documented external TLS/browser/auth/tenant/
mock/migration/restart/recovery checks. The existing `docs/STAGING.md` runbook and
Step 5G recovery tools govern deployment. No real AI, production credentials,
customer data or Step 5I work. No new source commit is authorized by this plan.

## Current prerequisites after final authorization

DigitalOcean authenticated account access has not been established in this task;
no doctl executable was found on PATH. Use secure browser/account access, never
paste an API token or SSH private key into chat. GitHub login is not DigitalOcean
login. Before creation establish the intended DigitalOcean project/account, public
SSH key and permitted SSH admin CIDR. Final creation authorization has been received for exactly
this one USD 24/month Singapore Basic Regular Droplet and the temporary sslip.io /
Let's Encrypt HTTPS strategy. Before creation the user explicitly requires asking
only for the selected SSH public key/name or safe public-key material and current
administrative public IP if unavailable. Neither has been supplied; standard local
.ssh directory is absent. No key generation/selection is inferred. No Droplet,
firewall, certificate or paid add-on has been created. Account authentication and
actual quote/capacity remain unverified; handle secure account access when needed.

The wildcard-DNS choice is deliberately **sslip.io** only. Verified
https://sslip.io/ redirects to https://nip.io/, whose operator documentation covers
both domains and states nip.io is incorporated into sslip.io. This explains the
previous documentation URL, rather than indicating two deployment providers.
The deployment suffix remains .sslip.io; no automatic alternate-service fallback.
Resolve the actual assigned IPv4 and obtain an individual trusted certificate.
If trusted issuance fails, stop as authorized and request a controlled subdomain.
This DNS-service relationship was checked against the operator's website and
https://github.com/cunnie/sslip.io. No actual-host DNS/TLS success is claimed.

## Sources checked

- [DigitalOcean pricing](https://www.digitalocean.com/pricing/droplets)
- [Droplet regional availability](https://docs.digitalocean.com/products/droplets/details/availability/)
- [Official OS images](https://docs.digitalocean.com/products/droplets/details/images/)
- [No-cost Cloud Firewalls](https://docs.digitalocean.com/products/networking/firewalls/)
- [Selected sslip.io operator documentation (redirects to shared nip.io site)](https://sslip.io/)
- [sslip.io operator source repository](https://github.com/cunnie/sslip.io)
- [Certbot standalone HTTP-01](https://eff-certbot.readthedocs.io/en/stable/using.html)

## Latest execution checkpoint: inputs received, account access blocked

The user supplied an approved Ed25519 public key and admin public IPv4. Key wire
format is valid: ssh-ed25519 with a 32-byte public key. Public-key fingerprint:
`SHA256:d1ILIWHR7kp271No4AOkUYaJ0aCC5fjcz+ZYSNKsocU`.
The public key and exact admin CIDR are retained only in ignored local deployment
artifacts. Use the approved address exclusively as TCP 22 source restriction;
never as the Droplet IP, application hostname or a broader allow rule. TCP 80/443
remain the only public web ports; approved key selection requires exact fingerprint
comparison in the provider before creation. No private key was requested/read.

Account-control checks: browser inventory returned no surfaces; attempts to open
in-app browser and Chrome reported unavailable. The official Windows computer-use
runtime failed native-pipe connection; one retry and session reset/reinitialization
also failed. doctl was absent from PATH and checked common installation locations.
No DigitalOcean account session, live creation quote, SSH-key selection or resource
inventory could be inspected. No paid Droplet, firewall, certificate or add-on was
created. No source transfer or remote command occurred. Restore an authenticated
DigitalOcean browser/control connection before execution; existing creation
approval remains valid and the SSH key/admin IP need not be requested again.

Exact-source archive checksum still matches its manifest; original leadforge.db
hash remains unchanged. Remote Step 5H is BLOCKED on account access, with all remote
checks unexecuted. Step 5I remains BLOCKED. No claim of zero resources already in
the user's account is made; zero resources were created by this task.

## Ready-message access recheck

After the user reported ready, browser inventory still returned zero browser/app
surfaces. Windows native-pipe discovery failed again, including the prescribed
retry and session reset/reinitialization. doctl remains unavailable on PATH.
DigitalOcean account access cannot be verified or used in this runtime. No creation
request or remote deployment was submitted. Existing approval and approved SSH
inputs remain valid; reconnect the computer/browser tool, or make an authenticated
DigitalOcean CLI available and provide its executable path without credentials.
