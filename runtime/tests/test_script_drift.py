"""Copy-drift guard — Brock's §0 rule 1, enforced (content drop item 4).

"Render verbatim. Copy changes come as a new version of this file." This test makes that a
CI-enforced property instead of a convention: every registry value that maps to a section of
`docs/build-kit/33_orchestration_script.md` is compared against the authored text in that
file. An edit made in the registry (or a silent "snappier" rewrite) fails here, NAMING the
key, so copy can only change by dropping in a new version of his file.

Keys marked UNMAPPED (rendered today, no counterpart in his v1) and ENG (mechanism, not
voice) are exempt by construction — there is nothing authored to compare them against, and
both are enumerated in the pull-in summary for him.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.agents.context_loader import load_orchestration_registry

_AUTHORED = (
    pathlib.Path(__file__).resolve().parents[2] / "docs/build-kit/33_orchestration_script.md"
)

# His authored strings live in markdown blockquotes; normalize away the quoting, smart quotes,
# bold markers and whitespace so the comparison is about WORDS, not formatting.
_NORMALIZE = [
    (re.compile(r"^\s*>\s?", re.MULTILINE), ""),  # blockquote markers
    (re.compile(r"\*\*"), ""),  # bold
    (re.compile(r"[“”]"), '"'),
    (re.compile(r"[‘’]"), "'"),
    (re.compile(r"\s+"), " "),
]


def _norm(text: str) -> str:
    for pattern, repl in _NORMALIZE:
        text = pattern.sub(repl, text)
    return text.strip().strip('"').strip()


def _authored_corpus() -> str:
    assert _AUTHORED.exists(), f"authored script missing: {_AUTHORED}"
    return _norm(_AUTHORED.read_text(encoding="utf-8"))


def _mapped_entries():
    """(key, entry) for every registry key that claims a §-section of his file."""
    return [
        (k, e) for k, e in load_orchestration_registry().items() if e.source.startswith("§")
    ]


def test_every_mapped_string_appears_verbatim_in_brocks_file():
    """The guard. A key whose text drifted from his authored copy fails BY NAME."""
    corpus = _authored_corpus()
    drifted: list[str] = []
    for key, entry in _mapped_entries():
        # Compare the literal parts around the variable slots: a {slot} may be filled with any
        # value, but every word between slots must be his, in his order.
        for fragment in [f for f in re.split(r"\{[a-z_]+\}", entry.text) if len(_norm(f)) > 12]:
            if _norm(fragment) not in corpus:
                drifted.append(f"{key} ({entry.source}): {_norm(fragment)[:70]!r}")
                break
    assert not drifted, "registry copy drifted from 33_orchestration_script.md:\n  " + "\n  ".join(
        drifted
    )


def test_mapping_covers_the_registry_and_names_real_sections():
    reg = load_orchestration_registry()
    unclassified = [k for k, e in reg.items() if not e.source]
    assert not unclassified, f"keys with no source marker: {unclassified}"
    for key, entry in reg.items():
        # Four provenance classes: §N.N = his orchestration script (drift-compared above) ·
        # CHECKLIST-* = his conformance checklist (a different authored doc, so not in the
        # script file) · UNMAPPED = rendered but unauthored · ENG = mechanism, not voice.
        assert entry.source.startswith(("§", "CHECKLIST", "UNMAPPED", "ENG")), f"{key}: {entry.source!r}"


# NOT hash-pinned, deliberately. There used to be a `test_authored_file_is_pinned_by_hash`
# here whose assertion ended in `or True` against a hash that never matched anything — an
# always-green test that looked like a guard (deep review nit 2). It's gone rather than
# repaired, because the thing it pretended to check is one we don't want: a byte hash of
# Brock's file would fail on every legitimate new drop, and it would tell us less than the
# per-key comparison above, which fails by KEY NAME and points straight at what moved.


@pytest.mark.parametrize(
    "key",
    ["attest.intro", "reconcile.last_resort", "decline.fabrication", "completion",
     "needs_documents_close", "handoff.generic_program"],
)
def test_spot_check_load_bearing_strings(key):
    """A handful of high-stakes strings checked explicitly, so a regression in the generic
    comparison above can't quietly let these through."""
    entry = load_orchestration_registry()[key]
    assert entry.source.startswith("§")
    corpus = _authored_corpus()
    longest = max(re.split(r"\{[a-z_]+\}", entry.text), key=len)
    assert _norm(longest) in corpus, f"{key} no longer matches his {entry.source}"
