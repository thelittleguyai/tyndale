"""Reading level of user-facing copy (doc 40 §A6) — a stdlib Flesch–Kincaid grade.

    grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59

No third-party dependency on purpose: the score gates CI, so it has to be the same number on
every machine and in every year. `textstat` swaps syllable dictionaries between releases; a
fifty-line heuristic does not move unless someone edits it.

Two things Flesch–Kincaid cannot do, and how the intake guard handles them:

* **Very short strings.** The formula is defined on prose. A one-word button ("Continue")
  scores grade 20; nobody needs a college degree to press it. Below ``PROSE_MIN_WORDS`` the
  guard uses the LABEL RULE instead: no word longer than ``LABEL_MAX_SYLLABLES`` syllables.
* **Terms the user must meet.** The packet allows "deductible", "coinsurance", "EOB",
  "out-of-pocket", "SBC", "MSN" — and the formal names printed on the documents — ONLY with a
  gloss on the same screen. A glossed term is swapped for a one-syllable stand-in before
  scoring (it still counts as a word, so sentence length stays honest).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GRADE_CEILING = 5.9
PROSE_MIN_WORDS = 7
LABEL_MAX_SYLLABLES = 3

# term id -> the surface forms it covers (longest first so "Explanation of Benefits (EOB)"
# is consumed whole). The id is what a screen's gloss slot is named after: a screen may use
# the "eob" forms only if it has an `intake.<screen>.gloss_eob` key.
GLOSSED_TERMS: dict[str, tuple[str, ...]] = {
    "eob": ("explanation of benefits (eob)", "explanation of benefits", "eobs", "eob"),
    "sbc": ("summary of benefits and coverage (sbc)", "summary of benefits and coverage", "sbc"),
    "msn": ("medicare summary notice (msn)", "medicare summary notice", "msn"),
    "deductible": ("deductibles", "deductible"),
    "coinsurance": ("coinsurance",),
    "out_of_pocket": ("out-of-pocket", "out of pocket"),
    "itemized": ("itemized",),
}
_STAND_IN = "plan"  # one syllable; never itself a glossed term

_VARIABLE = re.compile(r"\{[a-z_]+\}")
_TIER = re.compile(r"^\s*\[[ABC]\]\s*")
_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\$?\d[\d,.]*%?")
_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)|\n+")


# Words the vowel-group rules get wrong AND our copy actually uses. Keep it short: every entry
# is a word a reviewer can sound out. (CMU-style counts, the common pronunciation.)
_OVERRIDES: dict[str, int] = {
    "maybe": 2, "area": 3, "idea": 3, "create": 2, "created": 3, "real": 1, "really": 2,
    "people": 2, "business": 2, "every": 2, "everything": 3, "everyone": 3, "different": 2,
    "guard": 1, "guess": 1, "quiet": 2, "science": 2, "client": 2, "diet": 2, "via": 2,
    "tier": 1, "pier": 1, "fire": 1, "hour": 1, "our": 1, "ours": 1, "poem": 2, "lion": 2,
    "video": 3, "radio": 3, "ratio": 3, "aren't": 1, "isn't": 2, "doesn't": 2, "didn't": 2,
    "wasn't": 2, "hasn't": 2, "haven't": 2, "couldn't": 2, "wouldn't": 2, "shouldn't": 2,
    "reimburse": 3, "reimbursed": 3, "preexisting": 4, "coordinate": 4, "coinsurance": 4,
    "statement": 2, "statements": 2, "element": 3, "naive": 2, "something": 2, "sometimes": 2,
    "somewhere": 2, "someone": 2, "homepage": 2, "useful": 2, "careful": 2, "safely": 2,
    "likely": 2, "lately": 2, "surely": 2, "nicely": 2, "rarely": 2, "barely": 2,
    "anyone": 3, "anything": 3, "anywhere": 3, "anyway": 3,
}


def count_syllables(word: str) -> int:
    """Vowel groups, with the repairs English needs most: `y` as a consonant before a vowel
    ("paying"), silent final e ("share") but not after a vowel ("continue"), -ed/-es endings,
    a vowel before -ing ("going"), and the hiatus pairs io/ia/ua/eo ("period", "annual")."""
    raw = word.lower().replace("’", "'")
    if raw in _OVERRIDES:
        return _OVERRIDES[raw]
    if raw[:1].isdigit():
        return 1  # a figure is one beat for this purpose: "$1,200" is not a hard word
    w = re.sub(r"[^a-z]", "", raw)
    if not w:
        return 0
    if w in _OVERRIDES:
        return _OVERRIDES[w]
    if len(w) <= 3:
        return 1
    # `y` is a consonant at the start of a word and before a vowel
    v = re.sub(r"^y", "j", w)
    v = re.sub(r"y(?=[aeiou])", "j", v)
    n = len(re.findall(r"[aeiouy]+", v))
    if v.endswith("e") and v[-2] not in "aeiouy" and not v.endswith("le") and n > 1:
        n -= 1  # silent e: "share", "note" — but not "continue", "table"
    if v.endswith("ed") and not v.endswith(("ted", "ded", "ied")) and n > 1:
        n -= 1  # "asked", "billed" — "wanted", "needed" keep theirs
    if v.endswith("es") and not v.endswith(("ses", "zes", "ches", "shes", "xes", "ges", "ces", "ies")) and n > 1:
        n -= 1  # "rules", "notes" — "boxes", "charges" keep theirs
    if re.search(r"[aeiou]ing$", v):
        n += 1  # "going", "being", "seeing": the -ing is its own beat
    n += len(re.findall(r"(?<![ctsx])ia|io(?!n)|(?<![gq])ua|eo|iu", v))  # "media", "period", "annual"
    if re.search(r"[^aeiouy]e(?:ment|ments|less|ful|ness)$", v) and n > 1:
        n -= 1  # the e in "move-ment" is silent
    if len(v) > 4 and v.endswith(("ier", "iest")):
        n += 1  # "easier", "earlier"
    return max(1, n)


def _normalise(text: str, *, exempt: frozenset[str] = frozenset()) -> str:
    """Strip the tier tag and quotes; give variables a plain stand-in; swap exempt terms."""
    t = _TIER.sub("", text).strip().strip('"“”')
    t = _VARIABLE.sub("it", t)  # a variable renders as SOME short value; score the frame
    t = t.replace("—", ". ").replace("–", " ")  # a dash break reads as a pause, like a stop
    low = t.lower()
    for term in sorted(exempt):
        for form in GLOSSED_TERMS.get(term, ()):
            # replace case-insensitively, whole-form only
            pattern = re.compile(r"(?<![A-Za-z])" + re.escape(form) + r"(?![A-Za-z])", re.I)
            t = pattern.sub(_STAND_IN, t)
        low = t.lower()
    del low
    return t


def terms_used(text: str) -> set[str]:
    """Which glossed-term ids appear in this string (before any exemption)."""
    t = _VARIABLE.sub("it", _TIER.sub("", text)).lower()
    found: set[str] = set()
    for term, forms in GLOSSED_TERMS.items():
        for form in forms:
            if re.search(r"(?<![a-z])" + re.escape(form) + r"(?![a-z])", t):
                found.add(term)
                break
    return found


@dataclass(frozen=True)
class Reading:
    words: int
    sentences: int
    syllables: int
    max_word_syllables: int
    longest_word: str
    grade: float | None  # None below PROSE_MIN_WORDS — the label rule applies instead

    @property
    def is_prose(self) -> bool:
        return self.words >= PROSE_MIN_WORDS

    def passes(self) -> bool:
        if self.is_prose:
            return self.grade is not None and self.grade <= GRADE_CEILING
        return self.max_word_syllables <= LABEL_MAX_SYLLABLES

    def why(self) -> str:
        if self.is_prose:
            return f"FK grade {self.grade:.1f} > {GRADE_CEILING}"
        return (
            f"label rule: '{self.longest_word}' has {self.max_word_syllables} syllables "
            f"(max {LABEL_MAX_SYLLABLES} in a string under {PROSE_MIN_WORDS} words)"
        )


def read(text: str, *, exempt: frozenset[str] | set[str] = frozenset()) -> Reading:
    t = _normalise(text, exempt=frozenset(exempt))
    words = _WORD.findall(t)
    n_words = len(words)
    sentences = max(1, len([s for s in _SENTENCE_END.split(t) if _WORD.search(s or "")]))
    per_word = [(count_syllables(w), w) for w in words]
    syllables = sum(s for s, _ in per_word)
    top = max(per_word, default=(0, ""))
    grade = None
    if n_words >= PROSE_MIN_WORDS:
        grade = round(0.39 * (n_words / sentences) + 11.8 * (syllables / n_words) - 15.59, 1)
    return Reading(n_words, sentences, syllables, top[0], top[1], grade)


def screen_glosses(script: dict[str, str]) -> dict[str, frozenset[str]]:
    """screen id -> the glossed-term ids that screen may use: one per `intake.<screen>.gloss_<term>`
    key it carries. The exemption is EARNED by the gloss being on the same screen (§A6)."""
    out: dict[str, set[str]] = {}
    for key in script:
        parts = key.split(".")
        if len(parts) == 3 and parts[0] == "intake" and parts[2].startswith("gloss_"):
            out.setdefault(parts[1], set()).add(parts[2][len("gloss_") :])
    return {k: frozenset(v) for k, v in out.items()}


# Brock-AUTHORED intake strings that score over the ceiling. The rule for authored copy is
# "report it, don't rewrite it" (guided Phase 2 prompt, item F): each is pinned to its exact
# text, reported in docs/build-kit/reading_level_report.md, and exempt ONLY while that text is
# unchanged — his rewrite has to pass like any other intake string.
AUTHORED_OVER_CEILING: dict[str, str] = {
    # doc 41 §6 legend 3 — FK 10.6: "Individual" (5 syllables) in a 7-word line cut by "vs."
    "intake.example.accumulators.3": "Individual vs. family — these are different amounts.",
}


def _key_shape_ok(parts: list[str]) -> bool:
    """intake.<screen>.<slot>, or a numbered example legend intake.example.<doc>.<n> (doc 41)."""
    if len(parts) == 3:
        return True
    return len(parts) == 4 and parts[1] == "example" and parts[3].isdigit()


def check_intake_keys(script: dict[str, str]) -> list[str]:
    """Every problem with the `intake.*` keys, as "key: why" lines — empty means the set ships."""
    glosses = screen_glosses(script)
    problems: list[str] = []
    for key, text in script.items():
        if not key.startswith("intake."):
            continue
        parts = key.split(".")
        if not _key_shape_ok(parts):
            problems.append(f"{key}: key shape must be intake.<screen>.<slot> (or intake.example.<doc>.<n>)")
            continue
        allowed = glosses.get(parts[1], frozenset())
        unknown = {g for g in allowed if g not in GLOSSED_TERMS}
        if unknown:
            problems.append(f"{key}: gloss for an unknown term {sorted(unknown)}")
        unglossed = terms_used(text) - allowed
        if unglossed:
            problems.append(
                f"{key}: uses {sorted(unglossed)} but the '{parts[1]}' screen has no "
                f"intake.{parts[1]}.gloss_<term> key for it"
            )
            continue
        r = read(text, exempt=allowed)
        if not r.passes() and AUTHORED_OVER_CEILING.get(key) != text.strip():
            problems.append(f"{key}: {r.why()}")
    return problems
