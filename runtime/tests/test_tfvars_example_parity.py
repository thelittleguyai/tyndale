"""infra/envs/dev/terraform.tfvars.example must list EVERY declared variable (deep review 2/3).

It documented 11 of 70 and still described a Key Vault secret that had been removed — a file
whose whole job is to tell an operator what can be set, quietly covering a sixth of it. Every
variable now appears exactly once: uncommented when it is required (or deliberately set),
commented out with its default otherwise. Adding a variable without a line here fails."""

from __future__ import annotations

import pathlib
import re

DEV = pathlib.Path(__file__).resolve().parents[2] / "infra/envs/dev"
_VAR = re.compile(r'^variable\s+"([a-z0-9_]+)"\s*\{(.*?)^\}', re.MULTILINE | re.DOTALL)
_LINE = re.compile(r"^(# )?([a-z][a-z0-9_]*)\s+=\s+(.+)$", re.MULTILINE)


def _declared() -> dict[str, str]:
    return dict(_VAR.findall((DEV / "variables.tf").read_text(encoding="utf-8")))


def _example() -> list[tuple[bool, str, str]]:
    text = (DEV / "terraform.tfvars.example").read_text(encoding="utf-8")
    return [(bool(c), name, value.strip()) for c, name, value in _LINE.findall(text)]


def test_the_example_lists_every_declared_variable_exactly_once():
    declared = _declared()
    assert len(declared) >= 70, "variables.tf parsing is broken"
    names = [name for _, name, _ in _example()]
    assert sorted(set(declared) - set(names)) == [], "declared but missing from the example"
    assert sorted(set(names) - set(declared)) == [], "in the example but not declared"
    assert sorted(n for n in set(names) if names.count(n) > 1) == [], "listed more than once"


def test_required_variables_are_uncommented_and_optional_ones_show_their_default():
    declared = _declared()
    for commented, name, value in _example():
        default = re.search(r"^\s*default\s*=\s*(.+?)\s*$", declared[name], re.MULTILINE)
        if default is None:
            assert not commented, f"{name} is REQUIRED — it must be an uncommented placeholder"
        elif commented and default.group(1) != "{":
            assert value == default.group(1), f"{name}: example shows {value}, variables.tf says {default.group(1)}"


def test_sensitive_variables_only_ever_carry_placeholders():
    declared = _declared()
    for _, name, value in _example():
        if re.search(r"sensitive\s*=\s*true", declared[name]):
            bare = value.split(" #")[0].strip()
            assert bare == '""' or "REPLACE" in bare, f"{name} looks like a real value: {bare[:12]}…"


def test_the_google_client_id_is_described_as_the_plain_value_it_now_is():
    """dd94817 removed its Key Vault secret; the variable stayed and is passed as a plain env."""
    text = (DEV / "terraform.tfvars.example").read_text(encoding="utf-8")
    assert "google_oauth_client_id is NOT a Key Vault secret" in text
    compute = (DEV / "compute.tf").read_text(encoding="utf-8")
    assert "value = var.google_oauth_client_id" in compute  # plain value, not secret_name
    assert 'resource "azurerm_key_vault_secret" "google_oauth_client_id"' not in (
        DEV / "secrets.tf"
    ).read_text(encoding="utf-8")
