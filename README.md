# Ansible-Drupal-Role

Ansible roles that install a default Drupal instance (latest stable release) with all
required configuration and dependencies. At a high level this installs:

- nginx (default) or apache2
- PHP 8.3 + PHP-FPM
- MariaDB
- Composer
- Drush
- Drupal (latest stable release)
- Drupal modules as specified in `group_vars/all`

The goal is a base Drupal install with no errors on the status report.


### Compatibility

**Ubuntu 24.04 LTS (noble) only.**

The `common` role asserts this and fails immediately on anything else. Ubuntu 24.04
ships PHP 8.3 and MariaDB 10.11, which satisfy the requirements of current Drupal
releases. Earlier Ubuntu releases are no longer supported — support for 18.04/20.04
was removed along with the workarounds those releases needed.


### Requirements

On the **control machine**:

- Ansible (`brew install ansible` on macOS, `sudo apt install ansible` on Ubuntu)
- The collections in `requirements.yml`:

```bash
ansible-galaxy collection install -r requirements.yml
```

On the **target server**:

- Ubuntu 24.04 LTS with `python3` (present by default on Ubuntu Server)
- An SSH account with `sudo` access


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

There is no `db_root_password`. MariaDB's root account on Ubuntu authenticates through
the `unix_socket` plugin, so administrative tasks connect over the local socket as
system root. That is stronger than storing a root password in a vars file, and it means
one less secret to manage.


### TLS

Off by default. Enable it in `group_vars/all`:

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
  directory rather than certbot's nginx/apache plugins, so certbot never rewrites the
  vhost that Ansible manages.
- **`dns-01`** — proves control by writing a TXT record through the Cloudflare API.
  Use this when the server is internal, firewalled, or resolves to a private address,
  since it needs no inbound connectivity at all. Requires a Cloudflare API token
  scoped to `Zone:DNS:Edit` on the zone:

```yaml
webserver_tls_challenge: dns-01
webserver_tls_cloudflare_token: "{{ vault_cloudflare_token }}"
```

The vhost emits `http2 on;` or the older `listen ... ssl http2` form depending on the
installed nginx version — the standalone directive only exists from nginx 1.25.1, and
Ubuntu 24.04 ships 1.24.

Set `webserver_tls_staging: true` while testing. It issues an untrusted certificate
from the Let's Encrypt staging CA, which has far looser rate limits than production
(production allows only 5 duplicate certificates per week).


### PHP tuning

PHP settings are written as a drop-in at `/etc/php/<version>/{cli,fpm}/conf.d/99-drupal.ini`.
The packaged `php.ini` is never edited, so a PHP package upgrade cannot produce a
conffile prompt or silently revert these values.

Ubuntu's stock `memory_limit` (128M) and `max_execution_time` (30) are both low for
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

Limit to a subset of hosts:

```bash
ansible-playbook -i hosts --limit=host1 site.yml
```

The playbook is idempotent — a second run against a converged host reports zero
changes. Re-running is safe on a live site: Drupal is only installed when
`drush status` reports it is not already bootstrapped, and the hash salt is generated
once and never rewritten.


### Testing

After a deploy, run the smoke test:

```bash
ansible-playbook -i hosts tests/verify.yml
```

It asserts the web server, PHP-FPM and MariaDB are running, that the FPM socket exists
at the path the vhost points at, that the front page returns a rendered Drupal page
rather than a PHP error, that Drupal bootstraps, that the hash salt is non-empty, that
`settings.php` is not writable by the web server, and that the config sync directory is
where Drupal actually looks for it. It also reports any error-severity items on the
Drupal status report.

PHP settings are read via `php-fpm -i` rather than the `php` CLI, because the two SAPIs
load different `conf.d` directories — a CLI-based check would pass even if the FPM
drop-in were missing entirely.

When `webserver_tls_enabled` is true it additionally checks the HTTP-to-HTTPS redirect,
the certificate chain, HSTS, that Drupal is emitting `https://` URLs, that
`certbot.timer` is active, and that the certificate is not within two weeks of expiry.

Lint before committing:

```bash
ansible-lint && yamllint .
```


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
- **AVIF / GD library** — *not fixable on Ubuntu 24.04, by vendor policy.* Ubuntu
  deliberately builds `libgd2` without libavif: `libgd2` is in main, libavif's Rust
  dependency tree keeps it in universe, and main packages cannot build-depend on
  universe ([LP#2031934](https://bugs.launchpad.net/ubuntu/+source/libgd2/+bug/2031934)
  — the maintainer states no fix will be backported to stable releases). Debian's own
  libgd has AVIF enabled; this is Ubuntu-specific. Neither Ubuntu's `php8.3-gd` nor
  the ondrej PPA build contains AVIF support (verified by inspecting both binaries).
  Rebuilding libgd + ext/gd locally works but means privately maintaining two
  security-sensitive libraries that apt will silently revert on upgrade. If AVIF
  image derivatives are actually needed, use `php-imagick` with the ImageMagick
  toolkit contrib module (the path Drupal's own
  [AVIF issue](https://www.drupal.org/project/drupal/issues/3202016) endorses), or
  wait for a post-libavif-MIR Ubuntu release. Drupal's requirement is documented in
  [the AVIF change record](https://www.drupal.org/node/3348348) (Drupal 11.2.0).
  By default `tests/verify.yml` allows exactly this one item, by name, so that any
  *other* warning still fails the run. It can be resolved with an opt-in local
  build — see below.


### AVIF support in GD (opt-in, disabled by default)

Setting `php_gd_avif_build: true` compiles an AVIF-capable GD for PHP and clears the
last status report warning. It is off by default and should stay off unless you have
a concrete need for AVIF image derivatives.

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

- `webserver_type` selects `nginx` (default) or `apache`.
- The bare `php` metapackage is deliberately not installed. It depends on `php8.3`,
  whose first dependency alternative is `libapache2-mod-php8.3`, so apt pulls in
  apache2 as a side effect — which then binds port 80 and prevents nginx from starting.
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

- Apache TLS vhost is implemented but has only been tested with nginx
- Scheduled `drush cron` via a systemd timer. Cron currently runs only on install and
  when modules change; a long-running site needs it on a schedule.
- Database and files backups
- Splitting the web and DB tiers across separate hosts is wired up (`db_host` is a
  variable and no longer hardcoded to localhost) but has not been tested end to end.
  The DB user is still granted from `localhost` only.


### Contact

- john@johnmcgovern.com
- https://www.johnmcgovern.com
