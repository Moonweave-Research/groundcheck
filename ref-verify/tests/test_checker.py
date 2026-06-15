import unittest
from pathlib import Path

from checker import (
    ABSTRACT_LEVEL_ONLY,
    PARTIAL,
    TIER_1,
    TIER_2,
    UNVERIFIABLE,
    audit_claim,
    classify_claim_depth,
)

_FIXTURES = Path(__file__).parent / "fixtures"

# Expected new advisory content_status constants (contract strings).
# These are NOT imported from checker so the test file runs against the OLD
# checker without ImportError — the assertions that check for them are the
# RED gates that fail until checker.py is updated.
_TOPIC_MATCH = "TOPIC-MATCH — agent must confirm"
_CANDIDATE_SUPPORT = "CANDIDATE-SUPPORT — agent must confirm verbatim"
_POSSIBLE_CONTRADICTION = "POSSIBLE-CONTRADICTION — agent must check"
_PARTIAL_ADJACENT = "PARTIAL — adjacent keywords only"
_NO_CANDIDATE = "NO-CANDIDATE — no supporting sentence found"

# Legacy authoritative constants present in the OLD checker; used ONLY in
# negative assertions (the new contract forbids the checker from emitting them).
_SUPPORTED_ABSTRACT_LEVEL = "SUPPORTED (abstract-level)"
_SUPPORTED_FULL_TEXT = "SUPPORTED (full-text confirmed)"
_CONTRADICTED = "CONTRADICTED"
_UNSUPPORTED = "UNSUPPORTED — no full-text support found"

IONENE_ABSTRACT = """
Multifunctional ionene liquid crystal elastomers combine imidazolium backbones,
ionic liquid dopants, thermotropic actuation near 40 C, nascent electronic
conductivity, and self-sensing behavior.
"""

IONENE_FULL_TEXT = (_FIXTURES / "ionene_lce_pmc.txt").read_text(encoding="utf-8")

SULFUR_DIELECTRIC_FULL_TEXT = (_FIXTURES / "sulfur_dielectric.txt").read_text(
    encoding="utf-8"
)
FLUOROPOLYMER_ELECTRET_FULL_TEXT = (_FIXTURES / "fluoropolymer_electret.txt").read_text(
    encoding="utf-8"
)
IPMC_ACTUATOR_FULL_TEXT = (_FIXTURES / "ipmc_actuator.txt").read_text(encoding="utf-8")
FLUOROELASTOMER_FULL_TEXT = (_FIXTURES / "fluoroelastomer_electret.txt").read_text(
    encoding="utf-8"
)
HYDROGEL_ACTUATOR_FULL_TEXT = (_FIXTURES / "hydrogel_actuator.txt").read_text(
    encoding="utf-8"
)
PDMS_THERMAL_FULL_TEXT = (_FIXTURES / "pdms_thermal.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Invariant helper
# ---------------------------------------------------------------------------

_TIER2_SUPPORTED_STATUSES = {
    _SUPPORTED_FULL_TEXT,
    _SUPPORTED_ABSTRACT_LEVEL,
}


def _assert_tier2_warn_invariant(test: unittest.TestCase, result: dict) -> None:
    """Every Tier-2 result must have verdict WARN and must NOT be a SUPPORTED status."""
    test.assertEqual(result["depth"], TIER_2)
    test.assertEqual(
        result["verdict"],
        "WARN",
        f"Tier-2 verdict must always be WARN, got {result['verdict']!r}",
    )
    test.assertNotIn(
        result["content_status"],
        _TIER2_SUPPORTED_STATUSES,
        f"Tier-2 content_status must never be SUPPORTED*, got {result['content_status']!r}",
    )
    test.assertNotEqual(
        result["verdict"],
        "ACCEPT",
        "Tier-2 verdict must never be ACCEPT",
    )
    test.assertNotEqual(
        result["verdict"],
        "REJECT",
        "Tier-2 verdict must never be REJECT",
    )


# ---------------------------------------------------------------------------
# Claim depth classification (unchanged by the new contract)
# ---------------------------------------------------------------------------


class ClaimDepthTests(unittest.TestCase):
    def test_topic_claim_is_tier_1(self) -> None:
        claim = "This paper discusses ionene LCE actuation and self-sensing."

        self.assertEqual(classify_claim_depth(claim), TIER_1)

    def test_bulk_joule_heating_claim_is_tier_2(self) -> None:
        claim = "The LCE bulk itself Joule-heats by current through the bulk."

        self.assertEqual(classify_claim_depth(claim), TIER_2)


# ---------------------------------------------------------------------------
# Tier-1 (DEMOTED): topic match is now advisory TOPIC-MATCH/WARN, never ACCEPT
#
# RED against current (old) checker.py — old checker returns ACCEPT /
# SUPPORTED (abstract-level) for these cases.
# GREEN once checker.py is updated to the new advisory contract.
# ---------------------------------------------------------------------------


class Tier1Tests(unittest.TestCase):
    def test_tier1_topic_now_advisory(self) -> None:
        """Contract case tier1_topic_now_advisory: topic match -> TOPIC-MATCH/WARN.

        Was ACCEPT/SUPPORTED (abstract-level) in old checker. The checker only
        sees text and cannot authoritatively verify existence/metadata/DOI — so
        the Tier-1 path must surface the matched sentence and stay WARN.

        RED against old checker (returns ACCEPT / SUPPORTED (abstract-level)).
        """
        result = audit_claim(
            "This paper discusses ionene LCE actuation and self-sensing.",
            abstract_text=IONENE_ABSTRACT,
        )

        self.assertEqual(result["depth"], TIER_1)
        self.assertEqual(result["content_status"], _TOPIC_MATCH)
        self.assertEqual(result["verdict"], "WARN")
        self.assertNotEqual(result["verdict"], "ACCEPT")
        self.assertNotIn("SUPPORTED", result["content_status"])
        # The matched abstract sentence is surfaced for the agent to confirm.
        self.assertIn("ionene", result["evidence"].lower())

    def test_tier1_authored_by_kim_now_advisory(self) -> None:
        """H3 generic/structural split: bare 'by' attribution stays TIER_1 -> TOPIC-MATCH/WARN.

        RED against old checker (returns ACCEPT / SUPPORTED (abstract-level)).
        """
        claim = "The dataset was authored by Kim and released in 2024."
        abstract = (
            "This dataset of electret charge-decay curves was compiled by the Kim group "
            "and released openly in 2024."
        )

        result = audit_claim(claim, abstract_text=abstract)

        self.assertEqual(result["depth"], TIER_1)
        self.assertEqual(result["content_status"], _TOPIC_MATCH)
        self.assertEqual(result["verdict"], "WARN")
        self.assertNotEqual(result["verdict"], "ACCEPT")

    def test_tier1_existence_topic_match(self) -> None:
        """Contract case tier1_existence_topic_match: plain existence claim -> TOPIC-MATCH/WARN.

        RED against old checker (returns ACCEPT / SUPPORTED (abstract-level)).
        """
        claim = "This is the paper about halide-perovskite solar cells."
        abstract = (
            "Halide-perovskite thin-film solar cells have emerged as high-efficiency "
            "photovoltaic materials over the past decade."
        )

        result = audit_claim(claim, abstract_text=abstract)

        self.assertEqual(result["depth"], TIER_1)
        self.assertEqual(result["content_status"], _TOPIC_MATCH)
        self.assertEqual(result["verdict"], "WARN")
        self.assertNotEqual(result["verdict"], "ACCEPT")
        self.assertNotIn("SUPPORTED", result["content_status"])

    def test_tier1_partial_topic_off(self) -> None:
        """Contract case tier1_partial_topic_off: partial abstract match -> PARTIAL/WARN.

        Abstract mentions perovskite solar cells but not the specific record 30%
        tandem efficiency. Expected: PARTIAL/WARN regardless of old or new checker.
        """
        claim = "This paper reports a record 30 percent tandem efficiency."
        abstract = (
            "Halide-perovskite thin-film solar cells have emerged as photovoltaic "
            "materials over the past decade."
        )

        result = audit_claim(claim, abstract_text=abstract)

        self.assertEqual(result["depth"], TIER_1)
        self.assertEqual(result["content_status"], PARTIAL)
        self.assertEqual(result["verdict"], "WARN")

    def test_tier1_no_abstract_unverifiable(self) -> None:
        """No abstract -> UNVERIFIABLE/WARN; the checker clears nothing.

        Unchanged between old and new checker — expected GREEN against both.
        """
        result = audit_claim(
            "This paper discusses ionene LCE actuation and self-sensing.",
            abstract_text="",
        )

        self.assertEqual(result["depth"], TIER_1)
        self.assertEqual(result["content_status"], UNVERIFIABLE)
        self.assertEqual(result["verdict"], "WARN")

    def test_tier1_minimal_pair_connective_free_no_accept(self) -> None:
        """The decisive minimal pair: connective-free mechanism claim no longer ACCEPTs.

        'The enzyme cleaves the peptide bond' classifies TIER_1 (no connective);
        adding 'via hydrolysis' classifies TIER_2. Both must yield WARN with no
        SUPPORTED/ACCEPT — soundness is independent of the surface token.

        RED against old checker: no_via arm returns ACCEPT/SUPPORTED (abstract-level).
        """
        no_via = audit_claim(
            "The enzyme cleaves the peptide bond.",
            abstract_text=(
                "We characterize a serine protease. "
                "The enzyme cleaves the peptide bond at the active-site serine."
            ),
        )
        via = audit_claim(
            "The enzyme cleaves the peptide bond via hydrolysis.",
            full_text="The enzyme cleaves the peptide bond via hydrolysis at the active-site serine.",
        )

        self.assertEqual(no_via["depth"], TIER_1)
        self.assertEqual(via["depth"], TIER_2)
        for result in (no_via, via):
            self.assertEqual(result["verdict"], "WARN")
            self.assertNotEqual(result["verdict"], "ACCEPT")
            self.assertNotIn("SUPPORTED", result["content_status"])


# ---------------------------------------------------------------------------
# Tier-2 — no-source paths (UNCHANGED from current, still WARN)
# ---------------------------------------------------------------------------


class Tier2NoSourceTests(unittest.TestCase):
    def test_tier2_no_fulltext_abstract_level_only(self) -> None:
        """Tier-2 mechanism, no full text, abstract present -> ABSTRACT-LEVEL ONLY, WARN."""
        result = audit_claim(
            "The LCE bulk itself Joule-heats by current through the bulk.",
            abstract_text=IONENE_ABSTRACT,
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], ABSTRACT_LEVEL_ONLY)

    def test_tier2_no_source_unverifiable(self) -> None:
        """Tier-2 mechanism, neither abstract nor full text -> UNVERIFIABLE, WARN."""
        result = audit_claim(
            "The LCE bulk itself Joule-heats by current through the bulk.",
            abstract_text="",
            full_text="",
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], UNVERIFIABLE)


# ---------------------------------------------------------------------------
# Tier-2 — CANDIDATE-SUPPORT cases (formerly SUPPORTED/ACCEPT in old checker)
# RED until checker.py is updated to the new advisory contract
# ---------------------------------------------------------------------------


class Tier2CandidateSupportTests(unittest.TestCase):
    """Cases where checker must find a clean candidate sentence and emit CANDIDATE-SUPPORT/WARN.

    All were SUPPORTED/ACCEPT in the previous checker — they are now RED
    until checker.py implements the new advisory Tier-2 path.
    """

    def test_tier2_clean_candidate_sulfur(self) -> None:
        """Contract case tier2_clean_candidate_sulfur: verbatim sentence binds actor+action."""
        result = audit_claim(
            "The sulfur-rich copolymer bulk stores charge through deep trap states.",
            full_text=SULFUR_DIELECTRIC_FULL_TEXT,
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)
        # Checker must surface the verbatim binding sentence
        self.assertIn("sulfur", result["evidence"].lower())

    def test_tier2_clean_candidate_pvdf(self) -> None:
        """Contract case tier2_clean_candidate_pvdf: PVDF electret verbatim match."""
        result = audit_claim(
            "The PVDF electret retains surface charge via corona poling.",
            full_text=FLUOROPOLYMER_ELECTRET_FULL_TEXT,
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)
        self.assertIn("PVDF", result["evidence"])

    def test_tier2_clean_candidate_nafion(self) -> None:
        """Contract case tier2_clean_candidate_nafion: Nafion ion migration match."""
        result = audit_claim(
            "The Nafion membrane bends through ion migration under applied voltage.",
            full_text=IPMC_ACTUATOR_FULL_TEXT,
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)
        self.assertIn("Nafion", result["evidence"])

    def test_tier2_clean_candidate_lce_low_voltage_anchor(self) -> None:
        """Contract case tier2_clean_candidate_lce_low_voltage_anchor.

        The LM-electrode low-voltage case was the green SUPPORTED/ACCEPT anchor in
        old checker. Under the new contract even a perfectly paraphrase-bound sentence
        is only CANDIDATE-SUPPORT/WARN — the checker NEVER grants Tier-2 ACCEPT.

        RED against old checker (returns ACCEPT / SUPPORTED (full-text confirmed)).
        """
        result = audit_claim(
            "The LM electrode powered actuation at less than 3 V.",
            full_text=(
                "The controller modulated actuation by supplying a low voltage (<3 V) to the LM electrode."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)

    def test_tier2_threshold_just_above_now_candidate(self) -> None:
        """Contract case tier2_threshold_just_above_now_candidate.

        Was SUPPORTED/ACCEPT (threshold_just_above). Now CANDIDATE-SUPPORT/WARN.
        The old 0.75 augmented-overlap threshold gate is gone.
        """
        result = audit_claim(
            "The fluoroelastomer electret stabilizes trapped charge through chain dipoles.",
            full_text=FLUOROELASTOMER_FULL_TEXT,
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)

    def test_tier2_perovskite_harvests_now_candidate(self) -> None:
        """Contract case tier2_perovskite_harvests_now_candidate.

        D5a case (was ACCEPT after claim-derived stemming fix). Clean candidate
        clause -> CANDIDATE-SUPPORT/WARN.
        """
        result = audit_claim(
            "The perovskite layer harvests photons through bandgap absorption.",
            full_text=(_FIXTURES / "perovskite_photovoltaic.txt").read_text(
                encoding="utf-8"
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)

    def test_tier2_polysulfide_shuttles_now_candidate(self) -> None:
        """Contract case tier2_polysulfide_shuttles_now_candidate.

        D5b case (was ACCEPT). Clean candidate -> CANDIDATE-SUPPORT/WARN.
        """
        result = audit_claim(
            "The polysulfide shuttles lithium ions through the separator.",
            full_text=(_FIXTURES / "polysulfide_separator.txt").read_text(
                encoding="utf-8"
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)

    def test_tier2_enzyme_cobalt_now_warn_not_reject(self) -> None:
        """Contract case tier2_enzyme_cobalt_now_warn_not_reject.

        THE ENZYME CASE. Pass-2 object-noun contradiction scanner false-fired on
        'iron and manganese catalysts' and returned CONTRADICTED/REJECT. Now:
        sentence 2 is the clean candidate -> CANDIDATE-SUPPORT/WARN. The deleted
        object-noun scanner can no longer false-REJECT.
        Must be WARN, never REJECT.
        """
        result = audit_claim(
            "The cobalt catalyst activates molecular oxygen through a superoxide intermediate.",
            full_text=(_FIXTURES / "cobalt_catalyst.txt").read_text(encoding="utf-8"),
        )

        _assert_tier2_warn_invariant(self, result)
        # Must NOT be authoritative REJECT anymore
        self.assertNotEqual(result["verdict"], "REJECT")
        self.assertNotEqual(result["content_status"], _CONTRADICTED)
        self.assertEqual(result["content_status"], _CANDIDATE_SUPPORT)

    def test_tier2_passive_support_fragment_now_warn(self) -> None:
        """Contract case tier2_passive_support_fragment_now_warn.

        TEETH negation-branch case where the claim is actually TRUE: 'not merely
        as a passive support' is a rhetorical reinforcement. Pass-2 whole-sentence
        'not' poison withheld SUPPORTED. New contract: CANDIDATE-SUPPORT/WARN or
        POSSIBLE-CONTRADICTION/WARN — either is acceptable WARN. The invariant
        (no Tier-2 ACCEPT/SUPPORTED) is what matters.
        """
        result = audit_claim(
            "The carbon nanotube mat served as the Joule heater for the actuator.",
            full_text=(
                "The carbon nanotube mat served as the Joule heater for the actuator, "
                "not merely as a passive support."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        # Either CANDIDATE-SUPPORT or POSSIBLE-CONTRADICTION is acceptable
        self.assertIn(
            result["content_status"],
            {_CANDIDATE_SUPPORT, _POSSIBLE_CONTRADICTION},
            f"Expected CANDIDATE-SUPPORT or POSSIBLE-CONTRADICTION, got {result['content_status']!r}",
        )


# ---------------------------------------------------------------------------
# Tier-2 — POSSIBLE-CONTRADICTION cases (formerly CONTRADICTED/REJECT or false-ACCEPT)
# RED until checker.py is updated
# ---------------------------------------------------------------------------


class Tier2PossibleContradictionTests(unittest.TestCase):
    """Cases where the checker must flag a possible contradiction and emit WARN.

    These were either CONTRADICTED/REJECT (old authoritative path now demoted) or
    false-ACCEPT (D1/D2/D3/D4 false-ACCEPT family now correctly caught as WARN).
    All should be RED until checker.py implements the new advisory Tier-2 path.
    """

    def test_tier2_fails_to_now_warn(self) -> None:
        """Contract case tier2_fails_to_now_warn.

        'fails to' negation: pass-2 D1 case was correctly PARTIAL/WARN; the new
        contract expects POSSIBLE-CONTRADICTION/WARN (or PARTIAL/WARN). Checker
        must NEVER emit ACCEPT.
        """
        result = audit_claim(
            "The fluoroelastomer electret stabilizes trapped charge through chain dipoles.",
            full_text=(
                "The fluoroelastomer electret fails to stabilize trapped charge through "
                "chain dipoles, losing most of its surface potential within days."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_POSSIBLE_CONTRADICTION, _PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_precludes_now_warn(self) -> None:
        """Contract case tier2_precludes_now_warn.

        'precludes ... from' denial verb. The invariant (never ACCEPT/REJECT/SUPPORTED
        at Tier-2) holds regardless of which WARN annotation is emitted.
        Acceptable: POSSIBLE-CONTRADICTION, PARTIAL-adjacent, or PARTIAL.
        """
        result = audit_claim(
            "The copolymer bulk stores charge through deep trap states.",
            full_text=(
                "Backbone rigidity precludes the copolymer bulk from storing charge "
                "through deep trap states, so polarization is purely interfacial."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_POSSIBLE_CONTRADICTION, _PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_likely_untested_now_warn(self) -> None:
        """Contract case tier2_likely_untested_now_warn.

        'likely / remains untested' hedge: pass-2 false-ACCEPT (whole-sentence
        hedge-poison path). The new contract: not a clean candidate (hedged) ->
        step 4 or PARTIAL -> WARN.
        """
        result = audit_claim(
            "The PVDF electret retains surface charge via corona poling.",
            full_text=(
                "The PVDF electret likely retains surface charge via corona poling, "
                "but this mechanism remains untested in the present study."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_POSSIBLE_CONTRADICTION, _PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_neighbor_could_not_confirm_now_warn(self) -> None:
        """Contract case tier2_neighbor_could_not_confirm_now_warn.

        Pass-2 D2 'could not confirm' hedge false-ACCEPT. 'may' + 'could not
        confirm' -> not a clean candidate -> WARN (POSSIBLE-CONTRADICTION or PARTIAL).
        """
        result = audit_claim(
            "The PVDF electret retains surface charge via corona poling.",
            full_text=(
                "The PVDF electret may retain surface charge via corona poling, "
                "but our data could not confirm this."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_POSSIBLE_CONTRADICTION, _PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_role_swap_now_warn(self) -> None:
        """Contract case tier2_role_swap_now_warn.

        Pass-2 M3 role-swap false-ACCEPT (LCE claim, LM layer owns the action).
        Sentence 1 negates the claim actor; sentence 2 attributes action to LM layer.
        -> POSSIBLE-CONTRADICTION/WARN. NOT authoritative REJECT.
        """
        result = audit_claim(
            "The LCE served as the Joule heater.",
            full_text=(
                "The LCE did not serve as the Joule heater. "
                "The LM layer served as the Joule heater via the electrode."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_POSSIBLE_CONTRADICTION, _PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_hydrogel_competing_actor_now_warn_not_reject(self) -> None:
        """Contract case tier2_hydrogel_competing_actor_now_warn_not_reject.

        Was CONTRADICTED/REJECT in old checker. Silver nanowire network owns the
        heater action; hydrogel is marked passive. Now: POSSIBLE-CONTRADICTION/WARN —
        checker flags it for the agent rather than authoritatively REJECTing.
        """
        result = audit_claim(
            "The hydrogel bulk served as the Joule heater.",
            full_text=HYDROGEL_ACTUATOR_FULL_TEXT,
        )

        _assert_tier2_warn_invariant(self, result)
        # Must NOT be authoritative REJECT
        self.assertNotEqual(result["verdict"], "REJECT")
        self.assertNotEqual(result["content_status"], _CONTRADICTED)
        self.assertEqual(result["content_status"], _POSSIBLE_CONTRADICTION)

    def test_tier2_self_negating_cnt_now_warn(self) -> None:
        """Contract case tier2_self_negating_cnt_now_warn.

        CNT appears only under 'not'; liquid metal owns the action.
        -> POSSIBLE-CONTRADICTION/WARN or PARTIAL/WARN. Never ACCEPT.
        Acceptable alt: PARTIAL/WARN.
        """
        result = audit_claim(
            "The carbon nanotube mat served as the Joule heater for the actuator.",
            full_text="The liquid metal layer served as the Joule heater, not the carbon nanotube mat.",
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_POSSIBLE_CONTRADICTION, _PARTIAL_ADJACENT, PARTIAL},
        )


# ---------------------------------------------------------------------------
# Tier-2 — PARTIAL-adjacent cases
# ---------------------------------------------------------------------------


class Tier2PartialAdjacentTests(unittest.TestCase):
    def test_tier2_adjacent_keywords_only_partial(self) -> None:
        """Contract case tier2_adjacent_keywords_only_partial.

        No single sentence binds actor+action; only adjacent keywords.
        -> PARTIAL-adjacent / PARTIAL, WARN.
        """
        result = audit_claim(
            "The LCE bulk itself Joule-heats by current through the bulk.",
            full_text="The LCE showed conductivity. Joule heating was discussed in related soft actuators.",
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_word_salad_now_warn(self) -> None:
        """Contract case tier2_word_salad_now_warn.

        Pass-2 D3 scrambled word-salad false-ACCEPT (defeated only by the brittle
        actor-before-verb hard gate, now deleted). All keyword stems present but
        scrambled. Acceptable: PARTIAL/WARN or CANDIDATE-SUPPORT/WARN — both WARN.
        The invariant (no Tier-2 ACCEPT/SUPPORTED) is what matters.
        """
        result = audit_claim(
            "The copolymer bulk stores charge through deep trap states.",
            full_text=(
                "Stores charge through deep trap states the copolymer bulk does, "
                "the keyword index notes."
            ),
        )

        _assert_tier2_warn_invariant(self, result)
        # Either PARTIAL or CANDIDATE-SUPPORT is acceptable — both are WARN
        self.assertIn(
            result["content_status"],
            {_CANDIDATE_SUPPORT, _PARTIAL_ADJACENT, PARTIAL},
        )

    def test_tier2_threshold_below_now_warn(self) -> None:
        """Contract case tier2_threshold_below_now_warn.

        Low overlap, mechanism differs. No clean candidate -> PARTIAL/WARN.
        Acceptable alt: NO-CANDIDATE/WARN. The 0.75 threshold gate is gone.
        """
        result = audit_claim(
            "The fluoroelastomer electret stabilizes trapped charge through chain dipoles.",
            full_text="The fluoroelastomer electret lost charge rapidly under humid storage.",
        )

        _assert_tier2_warn_invariant(self, result)
        self.assertIn(
            result["content_status"],
            {_PARTIAL_ADJACENT, _NO_CANDIDATE, PARTIAL},
        )


# ---------------------------------------------------------------------------
# Tier-2 — NO-CANDIDATE case (formerly UNSUPPORTED/REJECT)
# RED until checker.py is updated
# ---------------------------------------------------------------------------


class Tier2NoCandidateTests(unittest.TestCase):
    def test_tier2_no_candidate_pdms(self) -> None:
        """Contract case tier2_no_candidate_pdms.

        On-topic material (PDMS) but mechanism ('suppresses charge injection /
        interface dipoles') appears nowhere in the full text; not even 2 overlapping
        mechanism keywords present.
        Was UNSUPPORTED/REJECT in old checker. Now: NO-CANDIDATE/WARN — checker
        NEVER emits an authoritative REJECT at Tier-2.
        """
        result = audit_claim(
            "The PDMS dielectric layer suppresses charge injection through interface dipoles.",
            full_text=PDMS_THERMAL_FULL_TEXT,
        )

        _assert_tier2_warn_invariant(self, result)
        # Must NOT be authoritative REJECT
        self.assertNotEqual(result["verdict"], "REJECT")
        self.assertNotEqual(result["content_status"], _UNSUPPORTED)
        self.assertEqual(result["content_status"], _NO_CANDIDATE)


# ---------------------------------------------------------------------------
# Cross-cutting soundness invariant over a REAL content-claim corpus
#
# REPLACES the old self-confirming meta-test. The old test only asserted WARN
# *if* the classifier had already labeled the input TIER_2 — a misclassified
# claim silently skipped every assertion, so the test could never catch the very
# leak it was meant to guard (a content claim escaping into an ACCEPT path).
#
# This corpus mixes connective-free and connective-bearing claims (including the
# enzyme via/no-via minimal pair and the lithium-dendrite case). The invariant
# is asserted UNCONDITIONALLY on audit_claim output — at ANY tier — so its
# correctness no longer depends on the classifier.
#
# RED against old checker: connective-free cases misclassify as TIER_1 and the
# old _audit_tier_1 ACCEPT branch fires, producing verdict ACCEPT and
# content_status "SUPPORTED (abstract-level)". GREEN once checker.py is updated.
# ---------------------------------------------------------------------------


class ContentClaimInvariantCorpusTests(unittest.TestCase):
    """Every real content/mechanism claim yields WARN, no ACCEPT, no SUPPORTED — at any tier."""

    # (name, claim, abstract, full_text). Each has matching abstract + full_text.
    _CORPUS = [
        # --- enzyme via/no-via minimal pair (the decisive surface-token flip) ---
        (
            "enzyme_cleaves_no_connective",
            "The enzyme cleaves the peptide bond.",
            "We characterize a serine protease. "
            "The enzyme cleaves the peptide bond at the active-site serine.",
            "The enzyme cleaves the peptide bond at the active-site serine, confirmed by mutagenesis.",
        ),
        (
            "enzyme_cleaves_via_hydrolysis",
            "The enzyme cleaves the peptide bond via hydrolysis.",
            "We characterize a serine protease that hydrolyzes amide bonds.",
            "The enzyme cleaves the peptide bond via hydrolysis at the active-site serine.",
        ),
        # --- lithium-dendrite case, connective-free and connective-bearing ---
        (
            "lithium_dendrite_no_connective",
            "The lithium anode forms dendrites during fast charging.",
            "Lithium-metal cells were cycled at 4C. "
            "The lithium anode forms dendrites during fast charging.",
            "The lithium anode forms dendrites during fast charging, imaged by operando microscopy.",
        ),
        (
            "lithium_dendrite_via_plating",
            "The lithium anode grows dendrites through uneven plating.",
            "Lithium-metal cells were cycled at 4C to probe morphology.",
            "The lithium anode grows dendrites through uneven plating at the electrolyte interface.",
        ),
        # --- connective-free content / finding claims ---
        (
            "sulfur_bulk_stores_charge_no_connective",
            "The sulfur copolymer bulk stores charge in deep trap states.",
            "A high-sulfur copolymer dielectric was prepared by inverse vulcanization.",
            "The sulfur copolymer bulk stores charge in deep trap states distributed throughout the network.",
        ),
        (
            "graphene_reduces_permeability_no_connective",
            "Graphene oxide reduces the membrane permeability.",
            "A laminated graphene-oxide membrane was fabricated. "
            "Graphene oxide reduces the membrane permeability markedly.",
            "Graphene oxide reduces the membrane permeability by nearly an order of magnitude.",
        ),
        # --- connective-bearing mechanism claims ---
        (
            "pvdf_retains_charge_via_corona",
            "The PVDF electret retains surface charge via corona poling.",
            "We report a PVDF electret for energy harvesting.",
            "The PVDF electret retains surface charge via corona poling at elevated temperature.",
        ),
        (
            "cobalt_activates_oxygen_via_superoxide",
            "The cobalt catalyst activates molecular oxygen through a superoxide intermediate.",
            "Single-atom cobalt catalysts were investigated for oxygen activation.",
            "The cobalt catalyst activates molecular oxygen through a superoxide intermediate, identified by EPR.",
        ),
        (
            "perovskite_harvests_photons_via_bandgap",
            "The perovskite layer harvests photons through bandgap absorption.",
            "Halide-perovskite solar cells were studied.",
            "The perovskite layer harvests photons through bandgap absorption across the visible spectrum.",
        ),
        # --- pure topic/existence claim (connective-free) ---
        (
            "mxene_topic_existence_no_connective",
            "This paper reports an MXene supercapacitor electrode.",
            "We report a Ti3C2 MXene supercapacitor electrode with high volumetric capacitance.",
            "The Ti3C2 MXene supercapacitor electrode delivered high capacitance over 10000 cycles.",
        ),
    ]

    def test_no_content_claim_yields_accept_or_supported(self) -> None:
        """Unconditional soundness invariant — checked at ANY tier, no classifier guard.

        RED against old checker: connective-free corpus cases (enzyme_cleaves_no_connective,
        lithium_dendrite_no_connective, graphene_reduces_permeability_no_connective,
        mxene_topic_existence_no_connective) misclassify as TIER_1 and the old
        _audit_tier_1 ACCEPT branch fires, yielding verdict ACCEPT and
        content_status "SUPPORTED (abstract-level)". The invariant assertion catches
        all of them.
        """
        for name, claim, abstract, full_text in self._CORPUS:
            with self.subTest(case=name):
                result = audit_claim(claim, abstract_text=abstract, full_text=full_text)
                self.assertEqual(
                    result["verdict"],
                    "WARN",
                    f"{name}: verdict must be WARN, got {result['verdict']!r}",
                )
                self.assertNotEqual(
                    result["verdict"],
                    "ACCEPT",
                    f"{name}: checker must never emit content ACCEPT",
                )
                self.assertNotIn(
                    "SUPPORTED",
                    result["content_status"],
                    f"{name}: content_status must never be SUPPORTED*, "
                    f"got {result['content_status']!r}",
                )

    def test_enzyme_minimal_pair_same_soundness_either_tier(self) -> None:
        """The minimal pair flips tier on one token but never flips soundness.

        RED against old checker: no_via arm returns ACCEPT / SUPPORTED (abstract-level).
        """
        no_via = audit_claim(
            self._CORPUS[0][1],
            abstract_text=self._CORPUS[0][2],
            full_text=self._CORPUS[0][3],
        )
        via = audit_claim(
            self._CORPUS[1][1],
            abstract_text=self._CORPUS[1][2],
            full_text=self._CORPUS[1][3],
        )

        self.assertEqual(no_via["depth"], TIER_1)
        self.assertEqual(via["depth"], TIER_2)
        for result in (no_via, via):
            self.assertEqual(result["verdict"], "WARN")
            self.assertNotEqual(result["verdict"], "ACCEPT")
            self.assertNotIn("SUPPORTED", result["content_status"])


# ---------------------------------------------------------------------------
# No-ACCEPT structural invariant
#
# RED against old checker: old checker.py defines `ACCEPT = "ACCEPT"` at module
# level and also defines `SUPPORTED_ABSTRACT_LEVEL`. Both must be absent from the
# new checker. These tests assert the module attributes are gone.
# ---------------------------------------------------------------------------


class NoAcceptConstantTests(unittest.TestCase):
    """The ACCEPT constant is removed; checker exports no content-ACCEPT symbol."""

    def test_checker_has_no_accept_constant(self) -> None:
        """RED against old checker: checker.ACCEPT exists and must be removed."""
        import checker

        self.assertFalse(
            hasattr(checker, "ACCEPT"),
            "checker.ACCEPT must be removed — there is no content ACCEPT at any tier.",
        )
        self.assertFalse(
            hasattr(checker, "SUPPORTED_ABSTRACT_LEVEL"),
            "checker.SUPPORTED_ABSTRACT_LEVEL must be removed — no SUPPORTED status anywhere.",
        )


if __name__ == "__main__":
    unittest.main()
