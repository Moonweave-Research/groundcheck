#!/usr/bin/env python3
"""Runnable, offline scenario eval for the ref-verify advisory checker.

The audit flagged evals/evals.json as a wishlist that never executed and never
called the checker. This is the executable layer it was missing: each case runs
audit_claim() against a recorded source (a fixture file or inline text — no
network), prints the advisory output, and asserts (a) the expected advisory flag
and (b) the global soundness invariant that holds for EVERY content claim — the
checker never emits an ACCEPT/REJECT verdict and never a SUPPORTED status. The
authoritative verdict is the agent's, per SKILL.md.

evals/evals.json remains the agent-level behavior spec (run the full skill on
those prompts and grade the prose). This file is the deterministic regression
floor under it.

Run from the skill root:
    PYTHONPATH=. uv run --no-project python3 evals/run_evals.py
Exits non-zero if any case fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from checker import audit_claim  # noqa: E402

_FIXTURES = _ROOT / "tests" / "fixtures"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


# Each case: claim, abstract, full_text, expected advisory content_status substring.
# Sources are recorded (fixture files / inline) so the eval is offline and stable.
_CASES = [
    {
        "name": "sulfur_bulk_stores_charge",
        "claim": "The sulfur-rich copolymer bulk stores charge through deep trap states.",
        "full_text": _fixture("sulfur_dielectric.txt"),
        "expect": "CANDIDATE-SUPPORT",
    },
    {
        "name": "pvdf_corona_poling",
        "claim": "The PVDF electret retains surface charge via corona poling.",
        "full_text": _fixture("fluoropolymer_electret.txt"),
        "expect": "CANDIDATE-SUPPORT",
    },
    {
        "name": "nafion_ion_migration",
        "claim": "The Nafion membrane bends through ion migration under applied voltage.",
        "full_text": _fixture("ipmc_actuator.txt"),
        "expect": "CANDIDATE-SUPPORT",
    },
    {
        "name": "cobalt_superoxide",
        "claim": "The cobalt catalyst activates molecular oxygen through a superoxide intermediate.",
        "full_text": _fixture("cobalt_catalyst.txt"),
        "expect": "CANDIDATE-SUPPORT",
    },
    {
        "name": "hydrogel_competing_actor",
        "claim": "The hydrogel bulk served as the Joule heater.",
        "full_text": _fixture("hydrogel_actuator.txt"),
        "expect": "POSSIBLE-CONTRADICTION",
    },
    {
        "name": "fluoroelastomer_fails_to",
        "claim": "The fluoroelastomer electret stabilizes trapped charge through chain dipoles.",
        "full_text": (
            "The fluoroelastomer electret fails to stabilize trapped charge through "
            "chain dipoles, losing most of its surface potential within days."
        ),
        "expect": "POSSIBLE-CONTRADICTION",
    },
    {
        "name": "pdms_off_topic_mechanism",
        "claim": "The PDMS dielectric layer suppresses charge injection through interface dipoles.",
        "full_text": _fixture("pdms_thermal.txt"),
        "expect": "NO-CANDIDATE",
    },
    {
        "name": "enzyme_topic_no_connective",
        "claim": "The enzyme cleaves the peptide bond.",
        "abstract": (
            "We characterize a serine protease. "
            "The enzyme cleaves the peptide bond at the active-site serine."
        ),
        "expect": "TOPIC-MATCH",
    },
    {
        "name": "enzyme_mechanism_via",
        "claim": "The enzyme cleaves the peptide bond via hydrolysis.",
        "full_text": "The enzyme cleaves the peptide bond via hydrolysis at the active-site serine.",
        "expect": "CANDIDATE-SUPPORT",
    },
]


def main() -> int:
    failures = 0
    for case in _CASES:
        result = audit_claim(
            case["claim"],
            abstract_text=case.get("abstract"),
            full_text=case.get("full_text"),
        )
        status = result["content_status"]
        verdict = result["verdict"]

        flag_ok = case["expect"] in status
        # Global soundness invariant — true for every content claim, any tier.
        invariant_ok = verdict not in {"ACCEPT", "REJECT"} and "SUPPORTED" not in status
        ok = flag_ok and invariant_ok
        failures += 0 if ok else 1

        tag = "PASS" if ok else "FAIL"
        print(
            f"[{tag}] {case['name']}: depth={result['depth']} verdict={verdict} status={status!r}"
        )
        if not flag_ok:
            print(f"       expected flag containing {case['expect']!r}")
        if not invariant_ok:
            print(
                "       INVARIANT VIOLATED: checker emitted an authoritative ACCEPT/REJECT/SUPPORTED"
            )

    total = len(_CASES)
    print(f"\n{total - failures}/{total} cases passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
