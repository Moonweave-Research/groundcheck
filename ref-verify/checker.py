#!/usr/bin/env python3
"""Advisory evidence surfacer for ref-verify.

This is NOT an authoritative gate. Two design passes established that a
regex/token heuristic cannot judge semantic support without false-ACCEPTs:
wherever authority rested on a heuristic (an overfit matcher, a cue list, the
tier classifier), an adversarial input slipped through. So the checker emits no
content ACCEPT or REJECT at any tier. It classifies claim depth as a hint,
surfaces the best candidate evidence sentence, and annotates the result with a
conservative advisory flag. Every content verdict is WARN; the authoritative
ACCEPT/WARN/REJECT belongs to the agent, which reads the surfaced sentence and
applies the verbatim-quote rule in SKILL.md. Soundness is therefore structural:
with no ACCEPT in any code path, a content false-ACCEPT is impossible by
construction, independent of how the claim is classified or matched.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


TIER_1 = "TIER_1"
TIER_2 = "TIER_2"

# Advisory content_status values. None of these is a SUPPORTED status; the
# checker never claims a citation is supported.
TOPIC_MATCH = "TOPIC-MATCH — agent must confirm"
CANDIDATE_SUPPORT = "CANDIDATE-SUPPORT — agent must confirm verbatim"
POSSIBLE_CONTRADICTION = "POSSIBLE-CONTRADICTION — agent must check"
PARTIAL_ADJACENT = "PARTIAL — adjacent keywords only"
NO_CANDIDATE = "NO-CANDIDATE — no supporting sentence found"
PARTIAL = "PARTIAL"
ABSTRACT_LEVEL_ONLY = "ABSTRACT-LEVEL ONLY — mechanism claim needs full text"
UNVERIFIABLE = "UNVERIFIABLE"

# The only verdict the checker ever emits for a content claim. There is no
# ACCEPT and no REJECT — those are the agent's to assign.
WARN = "WARN"

# Structural mechanism markers. Their presence routes a claim to the Tier-2
# (mechanism) hint path. Bare attribution prepositions ("by", "how", "where",
# "using", "measured", "conditions") are deliberately excluded: "authored by
# Kim" is metadata, not a mechanism claim. "via"/"through" are kept because they
# mark a mechanism relation. Misclassification only changes the advisory wording,
# never the soundness — so this list is a hint, not a gate.
_MECHANISM_PATTERNS = [
    r"\bvia\b",
    r"\bthrough\b",
    r"\bbulk\b",
    r"\bsurface\b",
    r"\bcoat(?:ed|ing)?\b",
    r"\belectrode\b",
    r"\bcurrent\b",
    r"\bpath\b",
    r"\bjoule\b",
    r"\bheater\b",
    r"\bvoltage\b",
    r"<\s*\d+\s*v\b",
    r"\bless than\s+\d+\s*v\b",
]

# Ambiguity cues. If any appears in a clause, that clause cannot be a clean
# candidate — a negated, hedged, conditional, or contrastive statement does not
# verbatim-support a claim. Bias is intentional: an ambiguous clause is steered
# to a WARN flag for the agent to read, never to silent support.
_CUE_PATTERNS = [
    r"\bnot\b",
    r"\bno\b",
    r"\bnever\b",
    r"\bcannot\b",
    r"\bcan ?not\b",
    r"\bunable\b",
    r"\bfails? to\b",
    r"\bfailed to\b",
    r"\bwithout\b",
    r"\bpreclud\w*",
    r"\bprevent\w*",
    r"\brather than\b",
    r"\binstead of\b",
    r"\bunlike\b",
    r"\bexcept\b",
    r"\bwhereas\b",
    r"\bonly if\b",
    r"\bonly when\b",
    r"\bunless\b",
    r"\bmay\b",
    r"\bmight\b",
    r"\bcould\b",
    r"\bwould\b",
    r"\blikely\b",
    r"\buntested\b",
    r"\bunconfirmed\b",
    r"\binconclusive\b",
    r"\bspeculat\w*",
    r"\bhypothes\w*",
    r"\bappears?\b",
    r"\bseems?\b",
    r"\bsuggests?\b",
    r"\bpresumably\b",
    r"\bpossibly\b",
]

_CLAUSE_SPLIT = re.compile(
    r"[;,]| but | however | yet | although | though | while | whereas "
)

_STOPWORDS = {
    "about",
    "and",
    "are",
    "at",
    "by",
    "can",
    "does",
    "for",
    "from",
    "how",
    "into",
    "itself",
    "less",
    "paper",
    "than",
    "that",
    "the",
    "this",
    "through",
    "via",
    "with",
}

_CANDIDATE_OVERLAP = 0.6
_RELATED_TERM_FLOOR = 2


@dataclass(frozen=True)
class AuditResult:
    depth: str
    content_status: str
    verdict: str
    evidence: str
    reason: str


def classify_claim_depth(claim: str) -> str:
    normalized = _normalize(claim)
    if any(re.search(pattern, normalized) for pattern in _MECHANISM_PATTERNS):
        return TIER_2
    return TIER_1


def audit_claim(
    claim: str,
    *,
    abstract_text: str | None = None,
    full_text: str | None = None,
) -> dict[str, str]:
    depth = classify_claim_depth(claim)
    if depth == TIER_1:
        return asdict(_audit_tier_1(claim, abstract_text))
    return asdict(_audit_tier_2(claim, abstract_text, full_text))


def _audit_tier_1(claim: str, abstract_text: str | None) -> AuditResult:
    if not abstract_text:
        return AuditResult(
            TIER_1,
            UNVERIFIABLE,
            WARN,
            "",
            "No abstract text was available for topic-level verification.",
        )

    sentence = _best_sentence(claim, abstract_text)
    if sentence and _term_overlap(claim, sentence) >= 0.5:
        return AuditResult(
            TIER_1,
            TOPIC_MATCH,
            WARN,
            sentence,
            "Abstract is on topic; confirm the paper exists and read the surfaced sentence.",
        )

    return AuditResult(
        TIER_1,
        PARTIAL,
        WARN,
        sentence or "",
        "Abstract is available but does not directly match the topic claim.",
    )


def _audit_tier_2(
    claim: str,
    abstract_text: str | None,
    full_text: str | None,
) -> AuditResult:
    if not full_text:
        if abstract_text:
            return AuditResult(
                TIER_2,
                ABSTRACT_LEVEL_ONLY,
                WARN,
                _best_sentence(claim, abstract_text),
                "Mechanism claim; full text not searched. Read the abstract sentence, then fetch full text.",
            )
        return AuditResult(
            TIER_2,
            UNVERIFIABLE,
            WARN,
            "",
            "Mechanism claim requires full text, but no source text was available.",
        )

    claim_terms = _terms(claim)
    actor = _claim_actor(claim)
    related_terms = claim_terms - {actor}
    sentences = _sentences(full_text)

    candidate = _find_clean_candidate(claim_terms, actor, sentences)
    if candidate:
        return AuditResult(
            TIER_2,
            CANDIDATE_SUPPORT,
            WARN,
            candidate,
            "A clause binds the claim actor and terms with no negation/hedge. Confirm it verbatim.",
        )

    flagged = _find_negated_or_competing(claim_terms, related_terms, actor, sentences)
    if flagged:
        return AuditResult(
            TIER_2,
            POSSIBLE_CONTRADICTION,
            WARN,
            flagged,
            "A clause negates the claim or assigns the action to a different actor. Check it.",
        )

    adjacent, overlap_terms = _find_adjacent(claim_terms, sentences)
    if len(overlap_terms) >= _RELATED_TERM_FLOOR:
        return AuditResult(
            TIER_2,
            PARTIAL_ADJACENT,
            WARN,
            adjacent,
            "Only adjacent keywords were found; no clause binds the claimed mechanism.",
        )

    return AuditResult(
        TIER_2,
        NO_CANDIDATE,
        WARN,
        "",
        "Full text was searched, but no supporting sentence was found.",
    )


def _find_clean_candidate(
    claim_terms: set[str], actor: str, sentences: list[str]
) -> str:
    best_sentence = ""
    best_overlap = 0.0
    for sentence in sentences:
        for clause in _clauses(sentence):
            clause_terms = _terms(clause)
            if actor not in clause_terms or _has_cue(clause):
                continue
            overlap = _overlap_fraction(claim_terms, clause_terms)
            if overlap >= _CANDIDATE_OVERLAP and overlap > best_overlap:
                best_overlap = overlap
                best_sentence = sentence
    return best_sentence


def _find_negated_or_competing(
    claim_terms: set[str],
    related_terms: set[str],
    actor: str,
    sentences: list[str],
) -> str:
    for sentence in sentences:
        for clause in _clauses(sentence):
            clause_terms = _terms(clause)
            if (
                _has_cue(clause)
                and len(claim_terms & clause_terms) >= _RELATED_TERM_FLOOR
            ):
                return sentence
    for sentence in sentences:
        for clause in _clauses(sentence):
            clause_terms = _terms(clause)
            if (
                actor not in clause_terms
                and len(related_terms & clause_terms) >= _RELATED_TERM_FLOOR
            ):
                return sentence
    return ""


def _find_adjacent(claim_terms: set[str], sentences: list[str]) -> tuple[str, set[str]]:
    union: set[str] = set()
    best_sentence = ""
    best_count = 0
    for sentence in sentences:
        shared = claim_terms & _terms(sentence)
        union |= shared
        if len(shared) > best_count:
            best_count = len(shared)
            best_sentence = sentence
    return best_sentence, union


def _claim_actor(claim: str) -> str:
    for token in re.findall(r"[a-z0-9]+", _normalize(claim)):
        if len(token) > 2 and token not in _STOPWORDS:
            return token
    return ""


def _best_sentence(claim: str, text: str) -> str:
    best_sentence = ""
    best_count = -1
    claim_terms = _terms(claim)
    for sentence in _sentences(text):
        shared = len(claim_terms & _terms(sentence))
        if shared > best_count:
            best_count = shared
            best_sentence = sentence
    return best_sentence


def _has_cue(text: str) -> bool:
    normalized = _normalize(text)
    return any(re.search(pattern, normalized) for pattern in _CUE_PATTERNS)


def _clauses(sentence: str) -> list[str]:
    return [
        part.strip() for part in _CLAUSE_SPLIT.split(f" {sentence} ") if part.strip()
    ]


def _sentences(text: str) -> list[str]:
    compact = " ".join(text.split())
    return [
        part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()
    ]


def _overlap_fraction(claim_terms: set[str], other_terms: set[str]) -> float:
    if not claim_terms:
        return 0.0
    return len(claim_terms & other_terms) / len(claim_terms)


def _term_overlap(claim: str, sentence: str) -> float:
    return _overlap_fraction(_terms(claim), _terms(sentence))


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:\s+sensing)?", _normalize(text))
        if len(token) > 2 and token not in _STOPWORDS
    }


def _normalize(text: str) -> str:
    normalized = text.lower()
    normalized = normalized.replace("≤", "<=")
    normalized = normalized.replace("∼", "~")
    normalized = normalized.replace("self-sensing", "self sensing")
    normalized = re.sub(r"<\s*(\d+)\s*v", r"<\1 v", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _read_optional(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Surface advisory evidence for a citation claim."
    )
    parser.add_argument("--claim", required=True)
    parser.add_argument("--abstract-file")
    parser.add_argument("--full-text-file")
    args = parser.parse_args()

    result = audit_claim(
        args.claim,
        abstract_text=_read_optional(args.abstract_file),
        full_text=_read_optional(args.full_text_file),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
