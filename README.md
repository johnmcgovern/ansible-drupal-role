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

Lint before committing:

```bash
ansible-lint && yamllint .
```


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

- Enable php.ini best-practices and tuning from `group_vars/all`
- TLS / certbot support
- Splitting the web and DB tiers across separate hosts is wired up (`db_host` is a
  variable and no longer hardcoded to localhost) but has not been tested end to end.
  The DB user is still granted from `localhost` only.


### Contact

- john@johnmcgovern.com
- https://www.johnmcgovern.com
