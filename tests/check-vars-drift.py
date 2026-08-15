#!/usr/bin/env python3
"""Compare group_vars/all against group_vars/all.sample.

The sample is the documentation: it is what we ask operators to copy and edit.
A real group_vars/all is created once and then rarely revisited, so as features
land it quietly falls behind. That drift is invisible in normal use because role
defaults cover the missing keys, which is by design -- but it means a host can be
running behaviour that its own vars file never mentions.

This reports the difference and, more usefully, says which parts of it matter:

  * A key in the sample but missing from group_vars/all is only worth acting on
    when the role default differs from what the sample documents. Otherwise the
    host behaves exactly as documented and nothing is wrong.
  * A key in group_vars/all that the sample never mentions -- not even as a
    commented example -- is an undocumented setting the next operator will not
    know to set.
  * Differing values are expected. That is what a local vars file is for.

Exits non-zero only for the two actionable cases, so it is usable in CI.

With no group_vars/all present (it is gitignored, so this is the normal state of
a fresh clone) it checks the sample on its own: every key the sample documents
should have a role default behind it, or omitting that key leaves the variable
undefined at runtime.

In both modes it also checks that every role defaults every configuration
variable it uses. Role defaults do not carry across plays, and site.yml runs its
four roles in four separate plays, so a variable defaulted only in roles/db is
undefined by the time roles/drupal renders settings.php with it. That works
anyway for anyone whose group_vars happens to set the key -- which is everyone
following the README -- and fails for anyone who does not, inside a no_log task,
with an error that does not name the variable. This is the check that makes each
role stand on its own instead of depending on where its caller keeps its vars.

Usage:
    tests/check-vars-drift.py
    tests/check-vars-drift.py --sample-only

Needs PyYAML, which comes with Ansible.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required (it ships with Ansible): pip install PyYAML")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(REPO, "group_vars", "all.sample")
LIVE = os.path.join(REPO, "group_vars", "all")

# Substrings that mark a variable as sensitive. Values are never printed for
# these; this script is meant to be safe to paste into an issue.
SECRET_HINTS = ("password", "token", "secret", "_key")

# Suffixes that make a match a false positive: these name an algorithm, a set of
# options or a path to something rather than holding a credential themselves.
# drupal_password_algorithm is "argon2id", and redacting it hides exactly the
# value someone running this needs to see.
NOT_SECRET_SUFFIXES = (
    "_algorithm",
    "_credentials",
    "_file",
    "_options",
    "_path",
    "_perms",
)

GREEN, YELLOW, RED, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    GREEN = YELLOW = RED = BOLD = RESET = ""


def is_secret(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith(NOT_SECRET_SUFFIXES):
        return False
    return any(hint in lowered for hint in SECRET_HINTS)


def show(key: str, value: object) -> str:
    """Render a value, redacting anything that looks sensitive."""
    if is_secret(key) and value not in (None, "", "CHANGEME"):
        return "<redacted>"
    return repr(value)


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def role_defaults() -> dict:
    """Every variable defined in a role's defaults/main.yml, with its source.

    First definition wins, matching the fact that these are only fallbacks: a
    variable set in more than one role's defaults resolves per-play anyway.
    """
    found: dict[str, tuple[object, str]] = {}
    for path in sorted(glob.glob(os.path.join(REPO, "roles", "*", "defaults", "main.yml"))):
        for key, value in load(path).items():
            found.setdefault(key, (value, os.path.relpath(path, REPO)))
    return found


# Keys within a task file whose value is a bare Jinja expression with no braces.
CONDITIONAL_KEYS = ("when", "failed_when", "changed_when", "that", "loop", "with_items")

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
JINJA_SPAN = re.compile(r"\{\{(.*?)\}\}|\{%(.*?)%\}", re.S)


def expressions(path: str) -> str:
    """Every Jinja expression in a file, concatenated.

    Only expressions, never whole lines: a comment that happens to name a
    variable is prose, not a dependency, and treating it as one would make this
    check cry wolf until somebody switched it off.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    spans = []
    if path.endswith((".yml", ".yaml")):
        lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
        text = "\n".join(lines)
        # Conditionals are Jinja without the braces, so they are not caught below.
        for line in lines:
            stripped = line.strip().lstrip("- ")
            for key in CONDITIONAL_KEYS:
                if stripped.startswith(f"{key}:"):
                    spans.append(stripped.split(":", 1)[1])

    for match in JINJA_SPAN.finditer(text):
        spans.append(match.group(1) or match.group(2) or "")
    return "\n".join(spans)


def role_dependencies(role: str, surface: set[str]) -> list[str]:
    """Config variables a role uses but does not default itself.

    Role defaults do not carry across plays. site.yml runs common, web, db and
    drupal in four separate plays, so a variable defaulted only in roles/db is
    simply undefined when roles/drupal renders settings.php with it -- and the
    failure surfaces inside a no_log task as an unexplained error. Every role
    has to stand on its own.

    A reference guarded by `| default(...)` carries its own fallback and does
    not need one in defaults/.
    """
    own = set(load(os.path.join(REPO, "roles", role, "defaults", "main.yml")))
    text = "\n".join(
        expressions(path)
        for pattern in ("tasks/*.yml", "handlers/*.yml", "templates/*")
        for path in sorted(glob.glob(os.path.join(REPO, "roles", role, pattern)))
    )

    missing = []
    for name in sorted(set(IDENTIFIER.findall(text)) & surface):
        if name in own:
            continue
        total = len(re.findall(rf"\b{name}\b", text))
        guarded = len(re.findall(rf"\b{name}\s*\|\s*default\s*\(", text))
        if total > guarded:
            missing.append(name)
    return missing


def check_role_self_sufficiency(sample: dict, defaults: dict) -> int:
    """Assert no role depends on another role's defaults across a play boundary."""
    surface = set(defaults) | set(sample)
    roles = sorted(
        os.path.basename(os.path.dirname(os.path.dirname(path)))
        for path in glob.glob(os.path.join(REPO, "roles", "*", "defaults", "main.yml"))
    )

    gaps: dict[str, list[str]] = {}
    for role in roles:
        # Secrets are deliberately undefaulted: the playbook asserts they are
        # set, so a missing password fails loudly rather than silently
        # provisioning a predictable account.
        missing = [n for n in role_dependencies(role, surface) if not is_secret(n)]
        if missing:
            gaps[role] = missing

    if not gaps:
        print(f"{GREEN}Every role defaults every config variable it uses.{RESET}")
        return 0

    print(f"{RED}Roles depending on a variable they do not default ({sum(map(len, gaps.values()))}){RESET}")
    print("  Role defaults do not carry across plays, so these are undefined at")
    print("  run time for anyone whose group_vars does not happen to set them.")
    for role, missing in gaps.items():
        for name in missing:
            source = defaults[name][1] if name in defaults else "nowhere"
            print(f"  - roles/{role} uses {name}, defaulted in {source}")
    return 1


def mentioned_in_comments(key: str, text: str) -> bool:
    """True when the sample documents a key as a commented-out example.

    Several settings are deliberately shown commented rather than set, because
    a wrong value is worse than an absent one -- the Cloudflare token and the
    trusted host patterns, for instance. Those still count as documented.
    """
    return any(
        line.lstrip().lstrip("#").lstrip().startswith(f"{key}:")
        for line in text.splitlines()
        if line.lstrip().startswith("#")
    )


def check_sample_only(sample: dict, defaults: dict) -> int:
    print(f"{BOLD}No group_vars/all found; checking the sample on its own.{RESET}\n")
    undefined = [k for k in sample if k not in defaults]

    # A handful of keys intentionally have no default: the playbook asserts they
    # are set rather than guessing, so that a missing password fails loudly
    # instead of silently provisioning a predictable account.
    required = [k for k in undefined if is_secret(k) or k.startswith("ansible_")]
    genuinely_undefined = [k for k in undefined if k not in required]

    if required:
        print(f"{GREEN}Documented with no role default, as intended ({len(required)}){RESET}")
        print("  (asserted at run time rather than defaulted)")
        for key in required:
            print(f"  - {key}")
        print()

    if genuinely_undefined:
        print(f"{RED}Documented but with no role default ({len(genuinely_undefined)}){RESET}")
        print("  Omitting these from group_vars/all leaves them undefined at run time.")
        for key in genuinely_undefined:
            print(f"  - {key}: sample says {show(key, sample[key])}")
        return 1

    print(f"{GREEN}Every documented key has a role default behind it.{RESET}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="check the sample against role defaults, ignoring any group_vars/all",
    )
    args = parser.parse_args()

    sample = load(SAMPLE)
    defaults = role_defaults()

    if args.sample_only or not os.path.exists(LIVE):
        return check_sample_only(sample, defaults) | check_role_self_sufficiency(sample, defaults)

    live = load(LIVE)
    sample_text = open(SAMPLE, encoding="utf-8").read()

    missing = [k for k in sample if k not in live]
    extra = [k for k in live if k not in sample]
    differing = [k for k in sample if k in live and sample[k] != live[k]]

    print(f"{BOLD}group_vars/all vs group_vars/all.sample{RESET}")
    print(f"  sample documents {len(sample)} keys; yours sets {len(live)}\n")

    # Missing keys only matter when the fallback differs from the documentation.
    benign, actionable = [], []
    for key in missing:
        if key not in defaults:
            actionable.append((key, "no role default -- would be undefined", None))
        elif defaults[key][0] != sample[key]:
            actionable.append((key, "role default differs from the sample", defaults[key]))
        else:
            benign.append((key, defaults[key]))

    if benign:
        print(f"{GREEN}Absent from yours, covered identically by role defaults ({len(benign)}){RESET}")
        print("  Nothing to do: these behave exactly as the sample documents.")
        for key, (value, _src) in benign:
            print(f"  - {key} = {show(key, value)}")
        print()

    if actionable:
        print(f"{RED}Absent from yours, and the fallback is not what the sample says ({len(actionable)}){RESET}")
        for key, why, default in actionable:
            got = f"  role default {show(key, default[0])} from {default[1]}" if default else ""
            print(f"  - {key}: {why}")
            print(f"      sample says {show(key, sample[key])}{got}")
        print()

    undocumented = [k for k in extra if not mentioned_in_comments(k, sample_text)]
    commented = [k for k in extra if k in extra and k not in undocumented]

    if commented:
        print(f"{GREEN}Set by you, shown in the sample as a commented example ({len(commented)}){RESET}")
        for key in commented:
            print(f"  - {key}")
        print()

    if undocumented:
        print(f"{RED}Set by you, absent from the sample entirely ({len(undocumented)}){RESET}")
        print("  The next operator has no way to know these exist.")
        for key in undocumented:
            print(f"  - {key} = {show(key, live[key])}")
        print()

    if differing:
        print(f"{YELLOW}Customised locally ({len(differing)}){RESET} -- expected, listed for review")
        for key in differing:
            print(f"  - {key}: sample {show(key, sample[key])} -> yours {show(key, live[key])}")
        print()

    rc = check_role_self_sufficiency(sample, defaults)
    print()

    if actionable or undocumented:
        print(f"{RED}Drift found that is worth acting on.{RESET}")
        return 1

    if rc:
        return rc

    print(f"{GREEN}No drift worth acting on.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
