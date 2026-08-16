# Ansible-Drupal-Role

[![Lint](https://github.com/johnmcgovern/ansible-drupal-role/actions/workflows/lint.yml/badge.svg)](https://github.com/johnmcgovern/ansible-drupal-role/actions/workflows/lint.yml)
[![Integration](https://github.com/johnmcgovern/ansible-drupal-role/actions/workflows/integration.yml/badge.svg)](https://github.com/johnmcgovern/ansible-drupal-role/actions/workflows/integration.yml)

Ansible roles that install a default Drupal instance (latest stable release) with all
required configuration and dependencies. At a high level this installs:

- nginx
- PHP + PHP-FPM (8.3 on 24.04 and RHEL 9, 8.5 on 26.04)
- MariaDB
- Composer
- Drush
- Drupal (latest stable release)
- Drupal modules as specified in `group_vars/all`

The goal is a base Drupal install with no errors on the status report.


### Compatibility

**Ubuntu 24.04 LTS (noble), Ubuntu 26.04 LTS (resolute) and RHEL 9.**

**nginx and MariaDB only.** Apache support was removed — it was never tested, and every
feature (TLS, PHP tuning, the GD build) had to carry a second untested code path. Anyone
still setting `webserver_type` gets an explicit error rather than a silent substitution.
The database is MariaDB; the roles assert the running server reports `MariaDB` and that
no MySQL or Percona packages are installed.

The `common` role asserts the platform and fails immediately on anything else. The two
Ubuntu releases are exercised by a blocking CI leg on every push, so that list and CI
cannot drift apart. RHEL is not, because GitHub offers no RHEL runner — it is validated
by hand, and the table below says so rather than implying a guarantee nothing enforces.
Every deploy onto a platform without a CI leg prints an EXPERIMENTAL warning naming that
gap. Earlier Ubuntu releases are not supported — 18.04/20.04 were dropped along with the
workarounds they needed.

#### Support matrix

| Platform | Status | PHP | MariaDB | nginx | Notes |
|---|---|---|---|---|---|
| Ubuntu 24.04 LTS (noble) | **Supported** — blocking CI leg | 8.3 | 10.11 | 1.24 | Reference platform |
| Ubuntu 26.04 LTS (resolute) | **Supported** — blocking CI leg | 8.5 | 11.8 | 1.28 | No `php-opcache` package; OPcache is built into PHP 8.5 |
| RHEL 9 | **Validated by hand** — no CI leg | 8.3 (module stream) | 10.11 (module stream) | 1.26 (module stream) | No TLS and no AVIF build; see below |
| RHEL 8.10 | **Not viable** | 8.2 max | 10.11 | 1.14 | AppStream tops out at PHP 8.2; Drupal 11 requires 8.3 |
| Rocky Linux 9 | *Future* | as RHEL 9 | as RHEL 9 | as RHEL 9 | Would likely need only an added platform identifier, but is untested |
| Amazon Linux 2023 | *Future* | 8.4 (`php8.4` packages) | MariaDB 10.5 | 1.24 | Different package naming again; no module streams |
| Ubuntu 18.04 / 20.04 / 22.04 | **Dropped** | — | — | — | Removed along with the workarounds they needed |

"Supported" means a blocking CI leg deploys and verifies the whole stack on every
push. Nothing else carries that guarantee — including RHEL, which is listed as
**validated by hand** precisely so the difference stays visible. What that means in
practice: the full sequence below was run against a real RHEL 9.7 host, and the roles
will not silently regress on Ubuntu because CI would catch it, but nothing automatically
catches a RHEL regression between releases.

Versions in the table above are what each platform shipped when it was last exercised:
Ubuntu 26.04 and RHEL 9 were read off the running hosts, Ubuntu 24.04 off CI.

#### Feature support by platform

Everything the roles do works everywhere except the two entries marked otherwise, both
of which fail with an explanation rather than deploying something untested.

| Feature | Ubuntu 24.04 | Ubuntu 26.04 | RHEL 9 |
|---|---|---|---|
| nginx, PHP-FPM, MariaDB, Composer, Drush | Yes | Yes | Yes |
| Drupal install, and `upgrade.yml` | Yes | Yes | Yes |
| PHP tuning drop-in | Yes | Yes | Yes |
| PHP-FPM pool tuning | Yes | Yes | Yes |
| systemd cron timer | Yes | Yes | Yes |
| systemd backup timer, and restore script | Yes | Yes | Yes |
| argon2id password hashing *(Drupal 11.4+)* | Yes | Yes | Yes |
| Trusted host patterns | Yes | Yes | Yes |
| **TLS via Let's Encrypt** | Yes | Yes | **No** — no certbot outside EPEL |
| **AVIF GD build** (`php_gd_avif_build`) | Yes | Yes | **No** — no libavif to build against |
| SELinux file contexts and booleans | n/a | n/a | Yes |
| firewalld port management | n/a | n/a | Yes |
| `php-opcache` as a separate package | Yes | n/a — built into PHP 8.5 | Yes |
| `uploadprogress` extension | Yes | Yes | No — EPEL only, and not required |

"n/a" means the platform has nothing for that feature to do, not that it is missing:
Ubuntu ships no nginx AppArmor profile and no firewall rules, and PHP 8.5 builds OPcache
into the interpreter. Neither case affects the deployed site.

The two **No** entries are the only functional differences. A RHEL host that needs HTTPS
should terminate TLS in front of it; a RHEL host that needs AVIF derivatives should use
`php-imagick` with Drupal's ImageMagick toolkit.

#### Drupal versions, and the PHP ceiling

Drupal's PHP requirement, not the distribution, is what decides whether a platform is
viable — it is why RHEL 8.10 is out. The same arithmetic has a near-term consequence for
two platforms in the table above:

| Drupal | Minimum PHP | Status |
|---|---|---|
| 11 (11.4.x current, 11.3.x also patched) | 8.3, 8.4 recommended | Current |
| 12 | **8.5** | Due the week of 7 December 2026 |

| Platform | Max PHP it ships | Drupal 11 | Drupal 12 |
|---|---|---|---|
| Ubuntu 24.04 | 8.3 | Yes | **No** |
| Ubuntu 26.04 | 8.5 | Yes | Yes |
| RHEL 9 | 8.3 (AppStream tops out here) | Yes | **No** |

Ubuntu 24.04 and RHEL 9 will not run Drupal 12 from distribution packages. Neither is
broken by this — Drupal 11 is current and fully supported — but both are pinned to the
11.x series for as long as they ship PHP 8.3, and the roles will not add a third-party
repository to change that, for the same reason they do not add EPEL for certbot.

The failure mode here is silence, so the roles say it out loud instead. Composer resolves
to the newest release whose platform requirement is satisfiable, so a PHP 8.3 host quietly
installs Drupal 11 and `upgrade.yml` keeps it there indefinitely, with nothing in the run
explaining why. Every deploy now reports the ceiling:

```
PHP 8.3 caps this host at Drupal 11.x. Drupal 12 requires PHP 8.5, which RedHat 9
does not ship. Installs and upgrades will stay on Drupal 11.x ...
```

Asking for a series the host cannot run is a different matter — that is a stated
intention, not an accident — so it fails immediately rather than part-way through a
Composer resolution: pinning `drupal_version` to a 12.x release, or running
`upgrade.yml -e upgrade_target='^12'`, stops before anything is installed or backed up
and names the PHP version it would need.

Package versions are what each distribution ships, but nothing here pins them. The PHP
version is discovered at runtime and every derived path (the FPM socket, the service
name, the `conf.d` directories) follows from it; the nginx vhost picks its `http2`
syntax from the installed nginx; and optional PHP packages are probed with the platform's
package manager rather than assumed. Three differences are worth knowing about:


- **OPcache.** `php-opcache` is a separate package through PHP 8.4 but does not exist on
  26.04, where PHP 8.5 builds OPcache into the interpreter. Naming a missing package
  aborts the whole transaction, so optional packages are installed only where the
  package manager offers them, and the play reports what it skipped.
- **AVIF.** Still absent from 26.04's `libgd3`, exactly as on 24.04, so the opt-in
  `php_gd_avif_build` remains relevant on both. It is unavailable on RHEL entirely.
- **Package names.** Almost nothing PHP-related is named the same way on RHEL:
  `php-mysql` is `php-mysqlnd`, APCu and zip are PECL builds, and there is no `php-curl`
  at all because curl is compiled into `php-common`. The lists live side by side in
  `roles/web/defaults/main.yml` rather than being translated at run time.

#### RHEL 9

Ported and validated by hand against a RHEL 9.7 host: a fresh install pinned to n-1,
`tests/verify.yml`, a second deploy asserting zero changes, `upgrade.yml` moving the site
to the current release, and `tests/verify.yml` again. There is no CI leg, so the matrix
above says "validated by hand" rather than "supported", and the play prints an
EXPERIMENTAL warning on every RHEL deploy.

The roles branch on `ansible_os_family` rather than forking. Most of the stack — Composer,
Drush, Drupal, the systemd units, the backup and restore scripts — was already
OS-agnostic and is untouched.

**What is different on RHEL**

- **Module streams.** AppStream's non-modular defaults are PHP 8.0 and MariaDB 10.5, both
  below Drupal 11's floor. `php:8.3`, `mariadb:10.11` and `nginx:1.26` are enabled
  explicitly before anything is installed. Enabling a stream also pins it, so dnf will
  not later move the host onto a different one.
- **Run-as account.** nginx runs as `nginx`, not `www-data`, and the packaged PHP-FPM
  pool runs as `apache` — a leftover of httpd being the assumed front end. The pool is
  repointed at the web server account, along with PHP's session and OPcache directories,
  which the packaging creates owned by `apache`. Leaving that alone produces a site that
  serves pages and then fails at its first cache write.
- **Paths.** `/etc/php.d` is flat and shared by every SAPI, so there is no CLI-vs-FPM
  split to get wrong; the drop-in is written once. The FPM socket is
  `/run/php-fpm/www.sock` and the service is `php-fpm`, both unversioned. The MariaDB
  socket is `/var/lib/mysql/mysql.sock` and its drop-in directory `/etc/my.cnf.d`. nginx
  has no `sites-available`, so the vhost is written straight into `conf.d`.
- **SELinux.** Enforcing, and left that way. The stock policy already labels
  `/var/www(/.*)?` as `httpd_sys_content_t`, so the codebase needs nothing; the two
  directories Drupal writes to get `httpd_sys_rw_content_t`, and
  `httpd_can_network_connect_db` is turned on so PHP-FPM can reach MariaDB. One case is
  easy to miss: `vendor/bin/drush` inherits a *content* type, and systemd refuses to
  execute a content type, so the cron timer dies with `203/EXEC` and a "Permission
  denied" naming a file that is plainly mode 0755. Composer's `vendor/bin` is therefore
  labelled `bin_t`, which is what those files actually are. `tests/verify.yml` asserts
  all four labels.
- **firewalld.** Active by default and blocking port 80, which Ubuntu does not do. Opened
  permanently and immediately — permanent alone writes the zone file without applying it,
  so the first deploy would finish with the port still shut.
- **MariaDB root authentication.** The "no root password anywhere" property does hold on
  RHEL, but not visibly: `mysql.user` reports root's plugin as `mysql_native_password`,
  which reads like a password account. The real record in `mysql.global_priv` shows that
  hash is the literal string `invalid` — unmatchable by any password — with `unix_socket`
  as the alternative. The db role now asserts this on both platforms rather than assuming
  it, because the alternative to checking is finding out later.
- **`/usr/local/bin` is not on the sudo path.** RHEL's `secure_path` omits it, so Composer
  is invoked by absolute path. Ubuntu's `secure_path` happens to include it, which is the
  only reason a bare `composer` ever worked.

**What is not available on RHEL**

- **TLS.** `webserver_tls_enabled: true` fails with an explanation instead of deploying.
  RHEL ships no certbot outside EPEL, and enabling a third-party repository on a
  subscription-managed host is not a side effect a CMS deployment should have. With EPEL
  the renewal timer is also named differently, so supporting it means a second code path
  with no way to test it — the cost that made Apache support worth deleting. Terminate
  TLS in front of the host instead.
- **The AVIF GD build.** `php_gd_avif_build: true` fails likewise. The build works by
  rebuilding the distribution's own libgd source package against libavif, and RHEL 9
  ships no libavif in BaseOS or AppStream. The GD warning on the status report is
  therefore permanent there; `php-imagick` with Drupal's ImageMagick toolkit is the
  alternative if you need AVIF derivatives.

**CI.** GitHub offers no RHEL runner. The options are a self-hosted runner, a
Rocky/Alma container — which reintroduces exactly the systemd-in-Docker problems the
current design avoids, and this stack is mostly systemd units — or accepting manual
validation and labelling it as such, which is what the matrix does.

Rocky Linux 9 and AlmaLinux 9 would likely need no more than an added entry in
`common_supported_releases`, since they share RHEL's packaging, but neither has been
tested and so neither is listed as working. Amazon Linux 2023 is a third dialect again:
no module streams, versioned `php8.4` package names, and its own MariaDB packaging.


### Requirements

On the **control machine**:

- Ansible (`brew install ansible` on macOS, `sudo apt install ansible` on Ubuntu)
- The collections in `requirements.yml`:

```bash
ansible-galaxy collection install -r requirements.yml
```

On the **target server**:

- Ubuntu 24.04 LTS, Ubuntu 26.04 LTS, or RHEL 9, with `python3` (present by default on
  Ubuntu Server and on RHEL)
- An SSH account with `sudo` access
- On RHEL: an active subscription, since PHP, MariaDB and nginx all come from AppStream.
  No third-party repository is added or required.


### Setup

1. Clone this project and change into it:

```bash
git clone https://github.com/johnmcgovern/ansible-drupal-role.git && cd ansible-drupal-role
```

2. Copy the sample inventory and variables:

```bash
cp hosts.sample hosts && cp group_vars/all.sample group_vars/all
```

3. Edit `hosts` to point at your server, and `group_vars/all` for your environment.
   Both files are gitignored.

Deploying more than one host? Put the shared configuration in `group_vars/all` and give
each host a `host_vars/<host>.yml` for what is genuinely its own — hostname, whether it
terminates TLS, which release it is pinned to — then run them one at a time with
`--limit`. `host_vars` outranks `group_vars`, so the shared file stays shared. A hostname
in `group_vars/all` makes that file a description of one machine and wrong for every
other, which is exactly the mistake worth avoiding. `host_vars/` is gitignored alongside
`hosts` and `group_vars/all`.

`group_vars/all.clean` is the same 40 settings with the explanations stripped down to
one-line section headings — 82 lines against the sample's 234. Copy that one instead if
you would rather read the configuration than the reasoning; the sample remains the
documentation, and `tests/check-vars-drift.py` treats the two as equivalent because they
carry identical keys and values.

```bash
cp group_vars/all.clean group_vars/all
```


### Secrets

`group_vars/all` contains at minimum `db_user_password` and `drupal_admin_password`.
Keep them out of plaintext by putting them in an encrypted file:

```bash
ansible-vault create group_vars/vault.yml
```

Put the secrets in `group_vars/vault.yml`, reference them from `group_vars/all`
(`db_user_password: "{{ vault_db_user_password }}"`), and run with `--ask-vault-pass`.
The playbook asserts both passwords are set and non-empty before it changes anything,
and the tasks that consume them use `no_log`.

There is no `db_root_password`. MariaDB's root account authenticates through the
`unix_socket` plugin on both platforms, so administrative tasks connect over the local
socket as system root. That is stronger than storing a root password in a vars file, and
it means one less secret to manage.

The db role asserts this rather than assuming it, because on RHEL it is not visible from
the obvious place: `mysql.user` reports root's plugin as `mysql_native_password`. The
authoritative record in `mysql.global_priv` shows that entry's hash is the literal string
`invalid`, which no password can produce, with `unix_socket` as the alternative. A
platform that genuinely did not configure socket authentication would fail the assertion
and say so, rather than having a stored root password quietly introduced to work around
it.


### TLS

Off by default, and **Debian-family only** — see the RHEL section above for why enabling
it on a Red Hat host fails with an explanation rather than deploying an untested path.

Enable it in `group_vars/all`:

```yaml
webserver_tls_enabled: true
webserver_tls_email: you@example.com
```

Enabling TLS redirects all HTTP traffic to HTTPS, serves HTTP/2, sends HSTS, and
passes `fastcgi_param HTTPS on` so Drupal generates `https://` URLs in links,
redirects and password reset mails. Certificates renew through the `certbot.timer`
that ships with the package, and a deploy hook reloads the web server when a renewal
actually happens.

Two validation methods are supported via `webserver_tls_challenge`:

- **`http-01`** (default) — certbot answers a challenge on port 80. Requires the host
  to be reachable from the internet. Uses `--webroot` against a dedicated ACME
  directory rather than certbot's nginx plugin, so certbot never rewrites the vhost
  that Ansible manages.
- **`dns-01`** — proves control by writing a TXT record through the Cloudflare API.
  Use this when the server is internal, firewalled, or resolves to a private address,
  since it needs no inbound connectivity at all. Requires a Cloudflare API token
  scoped to `Zone:DNS:Edit` on the zone:

```yaml
webserver_tls_challenge: dns-01
webserver_tls_cloudflare_token: "{{ vault_cloudflare_token }}"
```

The vhost emits `http2 on;` or the older `listen ... ssl http2` form depending on the
installed nginx version — the standalone directive only exists from nginx 1.25.1, so
24.04 (nginx 1.24) gets the listen-parameter form and 26.04 (nginx 1.28) the modern one.
The version is read from the running binary, so RHEL's 1.26 would be handled too if TLS
were available there.

Set `webserver_tls_staging: true` while testing. It issues an untrusted certificate
from the Let's Encrypt staging CA, which has far looser rate limits than production
(production allows only 5 duplicate certificates per week).


### PHP tuning

PHP settings are written as a drop-in named `99-drupal.ini`, in
`/etc/php/<version>/{cli,fpm}/conf.d` on Ubuntu and in the flat, SAPI-shared `/etc/php.d`
on RHEL. The packaged `php.ini` is never edited, so a PHP package upgrade cannot produce
a conffile prompt or silently revert these values.

The stock `memory_limit` (128M) and `max_execution_time` (30) are both low for
Drupal with a real module set, and `max_input_vars` (1000) silently truncates large
admin forms. The defaults here raise those, enable and size OPcache and APCu, and
grow the realpath cache. See `roles/web/defaults/main.yml` for the full list.

`php_upload_max_filesize` and `php_post_max_size` default to `webserver_max_body_size`
so the PHP and web server limits cannot drift apart — a mismatch produces confusing
413s at the boundary.

PHP-FPM process manager settings live in the pool file rather than php.ini and are set
individually via `php_fpm_pool_settings`, leaving the rest of the packaged pool intact.
Budget roughly `pm.max_children * php_memory_limit` as the worst-case memory use and
lower it on a small VM.


### Usage

```bash
ansible-playbook -i hosts site.yml
```

Install a specific Drupal release instead of the newest stable:

```yaml
drupal_version: "11.4.4"
```

This only affects a first install. Once `composer.json` exists the codebase is never
re-created, so changing it on an existing host does nothing — moving an installed site
forward is what `upgrade.yml` is for.

Limit to a subset of hosts:

```bash
ansible-playbook -i hosts --limit=host1 site.yml
```

The playbook is idempotent — a second run against a converged host reports zero
changes. Re-running is safe on a live site: Drupal is only installed when
`drush status` reports it is not already bootstrapped, and the hash salt is generated
once and never rewritten.


### Upgrading

`site.yml` never moves an installed site forward: it skips the codebase entirely once
`composer.json` exists, so a converged host stays on the release it was built with.
Upgrading is a deliberate, ordered operation with a database step in the middle, so it
is a separate playbook.

```bash
ansible-playbook -i hosts upgrade.yml                        # within current constraints
ansible-playbook -i hosts upgrade.yml -e upgrade_target='^11.5'   # to a new minor/major
```

It follows the documented Drupal sequence: take a backup, enter maintenance mode, update
the code with Composer, run `updatedb`, rebuild caches, leave maintenance mode. Running
`updatedb` against a live site risks serving requests through a half-migrated schema,
which is why the outage is deliberate. The database step is wrapped so that a failure
still takes the site back out of maintenance mode.

Moving across a minor or major also reconciles `allow-plugins`. Composer refuses to run
any plugin the project has not listed there, and that list is written once when
`create-project` scaffolds the site — `composer require` never revisits it. So a release
series that introduces a new plugin aborts the upgrade *after* rewriting `composer.json`,
leaving the constraint pointing at a release that is not installed. Observed moving
11.3.16 to `^11.4`, where 11.4's template adds `symfony/runtime`. The playbook fetches the
target release's own template and permits whatever it declares that the project lacks,
naming each one in the output; set `upgrade_sync_allow_plugins: false` to manage it by
hand.

Expect one manual step after a cross-minor upgrade. A newer release can deprecate a core
module that the older one enabled, and upgrading leaves it installed where a fresh install
of the newer release would not have it — moving 11.3 to 11.4 leaves `history` behind, for
instance. `tests/verify.yml` fails on it deliberately and names the module, because unlike
the GD/AVIF and update-fetch warnings this is something you can act on. Uninstalling it
drops data (`history` tracks per-user node read state), so it is not done automatically:

```bash
drush pm:uninstall history
```

The pre-upgrade backup is the rollback plan: Composer can be reverted from
`composer.lock`, but a failed `updatedb` cannot be undone without the database.
`drupal-restore.sh` restores exactly what it produces. Set `upgrade_backup: false` only
if you have just taken one by hand.

The playbook reports the version before and after, and asserts the site still bootstraps
afterwards. Re-running it when there is nothing to do reports
`11.4.5 -> 11.4.5 (no change: already at the newest release allowed by composer.json)`.


### The administrator account

`drupal_admin` and `drupal_admin_password` are applied by `site:install`, which runs only
when Drupal is not already installed. **Neither is reconciled on later runs** — changing
them in `group_vars/all` and re-deploying does nothing, by design, so a routine deploy
cannot reset a live site's administrator password. Change it with
`drush user:password <name> '<password>'` instead.

`drupal_admin_email` sets the address on the uid 1 account, defaulting to `drupal_email`.
Without it `site:install` falls back to Drush's own built-in `admin@example.com`, and
since that is where a password reset link goes, it is worth setting. Like the password, it
applies at install time only.


### Testing against an unreleased Drupal

`drupal_allow_unstable: true` permits a development or pre-release Drupal, which is how
you find out what a coming major does to a deployment before it ships. `drupal_version:
dev-main` installs Drupal 12's development branch — `drupal/recommended-project:dev-main`
requires `drupal/core-recommended:^12` — on any platform whose PHP is new enough, which
today means Ubuntu 26.04 only.

It is off by default and requesting a non-stable version without it fails with an
explanation, so a constraint copied from an issue thread cannot quietly install a
development snapshot. Drupal does not support running one: the code moves under you, and
there is no upgrade path off it short of reinstalling.

What a dry run of Drupal 12 currently shows, from a real deployment on 26.04:

- Core installs, `site:install` completes, and the site serves — the roles need no change
  for Drupal 12 itself.
- Contributed modules are the blocker, as expected this far ahead of release:
  `drupal/pathauto` and `drupal/ctools` still declare `drupal/core: ^8.8 || ^9`.
- `tests/verify.yml` **fails**, correctly. A dev snapshot reports "Unsupported release" at
  error severity, and errors are never allowlisted. A green verify on a development branch
  would mean the check was not working.

### Testing

After a deploy, run the smoke test:

```bash
ansible-playbook -i hosts tests/verify.yml
```

It asserts the web server, PHP-FPM and MariaDB are running, that the FPM socket exists
at the path the vhost points at, that the front page returns a rendered Drupal page
rather than a PHP error, that Drupal bootstraps, that the hash salt is non-empty, that
`settings.php` is not writable by the web server, and that the config sync directory is
where Drupal actually looks for it. It also checks the Drupal status report.

Status report items are judged by **severity, not title**. Warnings may be allowlisted by
name — the GD/AVIF one, and the update-status items, which report a fetch problem that
depends on Drupal's queue and drupal.org rather than on anything deployed here. Errors
never are. That distinction matters because Drupal files both the harmless and the
serious states under the same title: `Not secure!`, `Revoked!` and `Unsupported release`
are errors on the same "Drupal core update status" line that carries the flaky
fetch-pending warning, as is security coverage that has ended. Allowlisting by title
alone, as this once did, meant a site running a release with a known vulnerability
passed the smoke test. `Out of date` stays a tolerated warning: a newer release existing
is not a security problem, and failing on it would make the test fail as a function of
the upstream release calendar.

PHP settings are read via `php-fpm -i` rather than the `php` CLI. On Ubuntu the two
SAPIs load different `conf.d` directories, so a CLI-based check would pass even if the
FPM drop-in were missing entirely; RHEL shares one directory and so does not have that
trap, but the check goes through FPM on both, because what matters is what PHP-FPM
actually loaded.

On RHEL it additionally asserts that SELinux is enforcing rather than merely enabled —
otherwise every label assertion would pass regardless — that the four paths whose labels
matter carry the right types, that the SELinux booleans the stack needs are on, and that
firewalld is actually allowing the web ports.

It also refuses to run if the host is listening on port 443 while `webserver_tls_enabled`
is false. That combination means the TLS variables did not reach the playbook, and every
TLS assertion would be skipped while the run still reported success.

When `webserver_tls_enabled` is true it additionally checks the HTTP-to-HTTPS redirect,
the certificate chain, HSTS, that Drupal is emitting `https://` URLs, that TLS 1.0/1.1
are refused, that `certbot.timer` is active with its deploy hook installed, and that the
certificate is not within two weeks of expiry.

A live `certbot renew --dry-run` is available but off by default:

```bash
ansible-playbook -i hosts tests/verify.yml -e verify_check_renewal=true
```

It performs a real ACME transaction, so it takes a couple of minutes, counts against
Let's Encrypt rate limits, and fails intermittently on transient authorization state
that says nothing about the host. Everything else about renewal is checked offline.

Lint before committing:

```bash
ansible-lint && yamllint .
```

#### Checking group_vars for drift

`group_vars/all.sample` is the documentation, and a real `group_vars/all` is written
once and rarely revisited, so it falls behind as features land. The drift is invisible
in normal use because role defaults cover the missing keys — by design, but it means a
host can be running behaviour its own vars file never mentions.

```bash
tests/check-vars-drift.py
```

It separates the drift that matters from the drift that does not. A key missing from
your `group_vars/all` is only worth acting on when the role default differs from what
the sample documents; otherwise the host behaves exactly as documented. It fails only on
that case and on settings you have that the sample never mentions, so it is safe to run
in CI — and it redacts anything that looks like a credential, so the output is safe to
paste into an issue.

With no `group_vars/all` present it checks the sample alone, asserting every documented
key has a role default behind it. The lint workflow runs it in that mode.

In both modes it also asserts that **every role defaults every configuration variable it
uses**. Role defaults do not carry across plays and `site.yml` runs its four roles in
four separate plays, so a variable defaulted only in `roles/db` is undefined by the time
`roles/drupal` renders `settings.php` with it. That still works for anyone whose
`group_vars/all` sets the key — which is everyone who copied the sample — and fails for
anyone who does not, inside a `no_log` task, with an error that does not name the
variable. Keeping each role self-sufficient is what stops the deployment depending on
where its caller happens to keep its variables.

That dependency is easy to reintroduce, because it is invisible until someone runs the
roles a different way. The check exists so CI notices instead of a user.

#### Continuous integration

Two GitHub Actions workflows run on every push and pull request:

- **Lint** — `yamllint` and `ansible-lint` at the `production` profile.
- **Integration** — deploys the full stack and runs `tests/verify.yml`, as a matrix over
  Ubuntu 24.04 and 26.04. Both legs block. There is no RHEL leg, because GitHub offers
  no RHEL runner; see the RHEL section above for what is done instead. The runners are themselves the target OS with
  systemd, so the playbook runs against them directly rather than against a container;
  that avoids the systemd-in-Docker workarounds that would otherwise mask real problems
  with the timers and services this role installs.

The integration job runs the playbook **twice** and fails if the second run reports any
changes. That assertion is the one most likely to catch a regression, because a
non-idempotent task still looks fine on a first run.

CI copies `group_vars/all.sample` verbatim and layers CI-specific values on with `-e`,
so the sample is exercised on every run and cannot silently drift from what the roles
expect.


### Cron

Drupal needs cron for queue processing, cache expiry, search indexing and update
checks. A systemd timer (`drupal-cron.timer`) runs `drush cron` on a schedule, and
Drupal's `automated_cron` module is disabled by setting its interval to 0 — that module
only runs cron during page requests, so a visitor pays for it and there is no
scheduling guarantee.

```yaml
drupal_cron_enabled: true
drupal_cron_on_calendar: hourly   # any systemd OnCalendar expression, e.g. "*:0/15"
```

The timer uses `Persistent=true`, so a run missed while the host was down happens once
on boot rather than being skipped, and `RandomizedDelaySec` to add jitter.

The unit runs as the **web server account, not root**. Bootstrapping Drupal writes a
Twig cache under `sites/default/files`; doing that as root leaves files the web server
cannot subsequently rewrite. For the same reason every `drush` invocation in these
roles runs as that account (which is why `acl` is installed — Ansible needs it to hand
a temp file to an unprivileged `become_user`). `tests/verify.yml` asserts there are no
root-owned files under `files/`, so a regression here fails the run.

On deploy the unit is run once to prove it works under its own user and hardening,
rather than discovering a permissions problem at the first scheduled run.


### Backups

A systemd timer (`drupal-backup.timer`) dumps the database and archives the files
directory daily, keeping 14 days:

```yaml
drupal_backup_enabled: true
drupal_backup_path: /var/backups/drupal
drupal_backup_on_calendar: daily
drupal_backup_retention_days: 14
```

Each run produces four artefacts per timestamp: `.sql.gz`, `.files.tar.gz`,
`.settings.tar.gz` and a `.manifest`. The settings archive holds `settings.php` and the
hash salt — without the salt, a restore invalidates every session and one-time login
link.

**No database password is stored anywhere.** The dump runs as root through MariaDB's
`unix_socket` authentication, so there is no backup credentials file to leak or rotate.
It deliberately does not use drush: drush bootstraps Drupal, which writes a Twig cache
as the invoking user, and doing that as root recreates the root-owned-files problem the
cron work solved.

The backup directory is `0700 root:root`. The dumps contain every user record and the
settings archive contains the database password, so the web server must not be able to
read them — `tests/verify.yml` asserts this.

Cache table *contents* are excluded (schema is kept, since Drupal expects the tables to
exist); they are regenerated on demand and can dwarf the real data. Regenerable
`php/`, `css/` and `js/` directories are excluded from the files archive. Image
derivatives under `styles/` are kept — also regenerable, but rebuilding them all at
once after a restore is expensive.

#### Restoring

```bash
drupal-restore.sh --list          # show available backups
drupal-restore.sh                 # restore the most recent
drupal-restore.sh 20260812-143756 # restore a specific timestamp
```

It verifies both archives before destroying anything, replaces the files directory
rather than merging (so files deleted since the backup do not survive), fixes ownership,
and rebuilds caches. It asks for confirmation unless given `--force`. `settings.php` is
*not* overwritten automatically — the restore prints the command to do it manually,
since the running config is usually the one you want to keep.

This path is tested, not assumed: a canary node and file were created, backed up, then
the database was dropped and the files directory deleted, and both came back.


### Password hashing

Drupal hashes with PHP's `PASSWORD_DEFAULT` (bcrypt) unless told otherwise. Drupal 12
will default to argon2id and the status report recommends switching now, so these roles
configure it:

```yaml
drupal_password_algorithm: argon2id   # "" leaves PHP's default in place
drupal_password_options: {}           # PHP defaults: 64 MiB, 4 iterations, 1 thread
```

`PASSWORD_ARGON2ID` is available in Ubuntu 24.04's PHP 8.3, so this needs no third-party
packages.

**It requires Drupal 11.4 or newer.** Before 11.4 core declares the password service with
no arguments —

```yaml
password:
  class: Drupal\Core\Password\PhpPassword
```

— so it takes PHP's `PASSWORD_DEFAULT` and the `password.algorithm` parameter written into
`services.yml` is read by nobody. Setting `drupal_password_algorithm` on an older release
is not an error, it is simply inert, and the site keeps hashing with bcrypt. Nothing in
Drupal says so.

`tests/verify.yml` therefore checks the algorithm actually in use only where core can
honour it, and reports the skip rather than passing quietly:

```
Drupal 11.3.16 does not consume the password.algorithm container parameter -- it
gained that in 11.4 -- so drupal_password_algorithm (argon2id) has no effect here
and the site hashes with PHP's default.
```

Upgrading such a site to 11.4 switches it on with no configuration change: the parameter
was already in `services.yml` waiting to be read.

**Existing users are not locked out.** `password_verify()` reads the algorithm from the
hash itself, so bcrypt hashes keep validating; Drupal marks them as needing a rehash and
replaces them with argon2id on each user's next successful login. Both behaviours are
asserted in `tests/verify.yml`.

The value must be an identifier from PHP's `password_algos()` — `argon2id`, **not**
`PASSWORD_ARGON2ID`. Drupal checks it against that list and *silently falls back to the
PHP default* when it does not match, so a typo downgrades the site to bcrypt with no
error anywhere. `tests/verify.yml` therefore asserts the algorithm the container
actually built with and the prefix of a freshly generated hash, rather than trusting the
configuration file. That check is verified to fail when the value is wrong.

This is delivered through `sites/default/services.yml`, which is only read because
`settings.php` registers it in `$settings['container_yamls']` — core's
`default.settings.php` does this and the template here previously did not, so any
service or parameter override was silently ignored. Changing either file rebuilds the
Drupal cache, since both feed the compiled service container.


### Drupal status report

The goal is a clean status report out of the box. Three items that Drupal warns about
by default are handled:

- **Transaction isolation level** — MariaDB defaults to `REPEATABLE-READ`; Drupal
  recommends `READ-COMMITTED`. Set via a drop-in at
  `/etc/mysql/mariadb.conf.d/60-drupal.cnf`, along with `binlog_format = ROW`, which
  `READ-COMMITTED` requires if binary logging is ever enabled.
- **HTML5 validation** — leaving `enable_html5_validation` unset raises a warning
  because Drupal 12 will change its default. It is now set explicitly, defaulting to
  `false` to match that future default so a major upgrade cannot silently change how
  forms validate. Set `drupal_enable_html5_validation: true` to keep browser-side
  validation on.
- **AVIF / GD library** — *not fixable from distribution packages on either platform.*
  On RHEL there is simply no libavif in BaseOS or AppStream, so the warning is permanent
  and the opt-in build below is rejected. On Ubuntu it is vendor policy: Ubuntu
  deliberately builds `libgd2` without libavif: `libgd2` is in main, libavif's Rust
  dependency tree keeps it in universe, and main packages cannot build-depend on
  universe ([LP#2031934](https://bugs.launchpad.net/ubuntu/+source/libgd2/+bug/2031934)
  — the maintainer states no fix will be backported to stable releases). Debian's own
  libgd has AVIF enabled; this is Ubuntu-specific. Neither Ubuntu's `php8.3-gd` nor
  the ondrej PPA build contains AVIF support (verified by inspecting both binaries).
  Rebuilding libgd + ext/gd locally works but means privately maintaining two
  security-sensitive libraries. `php_gd_avif_build` does exactly that, opt-in and
  off by default; if you enable it, schedule a periodic playbook run, because the
  rebuild that recovers from a PHP ABI change only happens on a run. If AVIF
  image derivatives are actually needed, use `php-imagick` with the ImageMagick
  toolkit contrib module (the path Drupal's own
  [AVIF issue](https://www.drupal.org/project/drupal/issues/3202016) endorses), or
  wait for a post-libavif-MIR Ubuntu release. Drupal's requirement is documented in
  [the AVIF change record](https://www.drupal.org/node/3348348) (Drupal 11.2.0).
  By default `tests/verify.yml` allows exactly this one item, by name, so that any
  *other* warning still fails the run. It can be resolved with an opt-in local
  build — see below.


### AVIF support in GD (opt-in, disabled by default, Ubuntu only)

Setting `php_gd_avif_build: true` compiles an AVIF-capable GD for PHP and clears the
last status report warning. It is off by default and should stay off unless you have
a concrete need for AVIF image derivatives.

**Ubuntu only.** The whole approach depends on rebuilding the distribution's own libgd
source package against libavif, and RHEL 9 ships neither, so enabling it on a Red Hat
host fails with that explanation rather than attempting a build that cannot succeed.

How it works: Ubuntu's own `debian/rules` already passes `--with-avif`, and
`libavif-dev` is in the archive — the package simply is not built against it. The role
fetches Ubuntu's `libgd2` and `php8.3` sources with `apt-get source`, builds libgd into
a private prefix (`/opt/gd-avif`) with AVIF enabled, builds `ext/gd` against it via
`phpize` with an rpath to that prefix, and repoints PHP's `20-gd.ini` at the result.

The system `libgd3` is **not** touched. It stays exactly as apt installed it, which
avoids the trap of a locally built package carrying the same version string as the
official one and being silently reverted on the next upgrade. `tests/verify.yml`
asserts `dpkg -V libgd3` still passes, so a regression there fails the run.

The build self-tests by encoding a real AVIF image and aborts if that fails, leaving
the distribution GD module in place — a failed build cannot break the site. Setting the
flag back to `false` restores the distribution module.

**What you take on by enabling it:**

- libgd and libavif security updates no longer reach the copy PHP loads. apt will keep
  patching the system `libgd3`; it will not touch this build. You are tracking those
  advisories yourself.
- A PHP upgrade that changes the extension ABI needs a rebuild. A build stamp records
  the PHP ABI and libgd version and triggers one automatically, but between the apt
  upgrade and the next playbook run PHP will fail to load GD. Ubuntu 24.04 stays on PHP
  8.3 for its supported life, so in practice this means point releases, which do not
  change the ABI.
- Roughly 250 MB of build tooling is installed on the target and stays there.
- Ubuntu does not support this configuration.

If you want AVIF derivatives but not the maintenance, `php-imagick` with the
ImageMagick toolkit contrib module is the supported route. It will not clear the GD
warning, because Drupal checks GD regardless of the active toolkit.


### Notes

- The bare `php` metapackage is deliberately not installed. It depends on `php8.3`,
  whose first dependency alternative is `libapache2-mod-php8.3`, so apt would pull in
  Apache as a side effect — which then binds port 80 and prevents nginx from starting.
  `php-cli` provides the same interpreter with no web server attached.
- `drupal_trusted_host_patterns` is an empty list by default, which disables Drupal's
  host header protection and leaves one warning on the status report. Set it to a list
  of regular expressions once your hostname is settled. An incorrect pattern makes the
  site unreachable, which is why it is opt-in.
- The Drupal code is owned by `root` and readable by the web server group. Only
  `web/sites/default/files` and `config/sync` are writable by the web server, so a PHP
  vulnerability cannot rewrite the application code.
- The Composer installer is checksum-verified against the signature Composer publishes
  before it is executed.
- The hash salt lives in `{{ drupal_base_path }}/.hash_salt`, outside the docroot, and
  `settings.php` reads it at runtime.


### ToDo

- Splitting the web and DB tiers across separate hosts is wired up (`db_host` is a
  variable and no longer hardcoded to localhost) but has not been tested end to end.
  The DB user is still granted from `localhost` only.


### Contact

- john@johnmcgovern.com
- https://www.johnmcgovern.com
