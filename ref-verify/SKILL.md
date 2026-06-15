---
name: ref-verify
description: "Prevents citation hallucination in academic writing. Invoke when: finding papers to support a specific claim; verifying/checking/auditing existing citations or DOIs; confirming whether a paper actually says what the user claims it says ('is that what the paper says?', 'did they actually show X?'); adding a citation by describing a paper ('add a citation for the paper where X'); running a pre-submission reference sweep. Do NOT invoke for: formatting references in APA/IEEE style, general topic explanations, citation style questions, or prose editing. Selects Quick Screen (seconds per paper) or Full Audit (abstract/full-text claim check) automatically."
---

# ref-verify — Reference Hallucination Guard

The specific failure this skill prevents: LLMs describe paper content from recalled training data rather than from what live-fetched source text actually says. A paper gets attributed findings it doesn't contain, or cited for claims that appear nowhere in the text. The fix is one rule applied consistently:

**Every content statement about a paper must come from live-fetched source text, quoted verbatim from the fetched text to assign SUPPORTED, and paraphrased only from the fetched text (never from memory) for any softer description. Abstracts are enough only for existence/topic-level claims. Mechanism or implementation claims require full text. If you cannot fetch the needed source text, say so explicitly — never fill the gap with recalled description.**

---

## Mode Decision

Pick the mode before doing any work. The choice controls cost and depth.

```
User provides DOI(s) for sanity check?
  └─ ≤10 refs → Quick Screen all
  └─ >10 refs → Quick Screen all; Full Audit only MISMATCH/DEAD results

User says "find papers on X" or "cite papers supporting claim Y"?
  └─ Full Audit (searching from scratch requires content verification)

User says "verify/check my reference list" or pre-submission audit?
  └─ ≤5 refs  → Full Audit all
  └─ >5 refs  → Quick Screen all first; Full Audit MISMATCH/DEAD + any ref
                 cited for a specific factual claim

User is writing inline and adds a single citation from memory?
  └─ Quick Screen minimum; Full Audit if citing for a specific claim
```

The expensive part is Full Audit (5-layer, abstract/full-text fetch when needed). Quick Screen costs ~5s per paper. Only escalate to Full Audit when the task genuinely requires content verification. In Full Audit, classify claim depth before Layer 3: mechanism-level claims make full-text fetch mandatory, not optional.

---

### Quick Screen — metadata + DOI sanity check

Use when the user provides a DOI or full citation and wants a sanity check.

1. Hit CrossRef: `https://api.crossref.org/works/{DOI}`
2. Compare returned title + first-author last name against what user provided
3. Fetch `https://doi.org/{DOI}` — confirm it resolves and lands on the right paper
4. Report one line per reference:

```
Smith et al. (2021) 10.1234/example — PASS (title/author match, DOI resolves)
Jones (2019) 10.5678/other — MISMATCH (CrossRef: Jones & Lee 2019, not Jones alone)
Kim (2023) 10.9999/fake — DEAD DOI
```

Escalate to Full Audit if: DOI resolves to a different paper, any field mismatches, or user is citing for a specific factual claim.

---

### Full Audit — for literature search or pre-submission check

Use when: searching for papers to support a claim, or doing a final citation sweep.

Run all five layers per paper. The layers are ordered by what they catch — don't skip forward.

**Layer 1 — Existence**

Search two sources independently. Use CrossRef and OpenAlex as the two-source baseline:
- CrossRef: `https://api.crossref.org/works?query.bibliographic={title+author}&rows=5`
- OpenAlex: `https://api.openalex.org/works/doi:{DOI}` — no auth required; returns `title`, `authorships`, `publication_year`, `abstract_inverted_index`, and `is_retracted`. Also usable as a title search via `https://api.openalex.org/works?filter=title.search:{title}`.
- Semantic Scholar: `https://api.semanticscholar.org/graph/v1/paper/search?query={title+author}&fields=title,authors,year,externalIds,abstract&limit=5` — treat as optional; S2 frequently returns HTTP 429 without an API key, in which case fall back to CrossRef + OpenAlex alone.
- arXiv for preprints: `https://export.arxiv.org/api/query?search_query=ti:{title}&max_results=3` — the arXiv search API treats `+` as OR; URL-encode spaces as `%20` (or join multi-word terms with explicit `AND`, e.g. `ti:flexible%20AND%20actuator`) so that a multi-word title does not return false positives from single-keyword matches.

A paper is confirmed only if titles essentially match and first-author last name agrees across two sources.

- Two-source hit → `CONFIRMED`
- One-source → `SINGLE-SOURCE ⚠` — proceed with caution, note in output
- Zero → `NOT FOUND ✗` — stop; report clearly; do not invent a substitute

**Layer 2 — Metadata**

Extract from confirmed sources and compare: title, all authors (last names), year, journal full name, DOI, volume/pages (mark `[NOT IN SOURCE]` if absent). If any field differs between sources, show both — do not silently pick one.

Author-name caveats — flag, do not auto-reject, when:
- CJK names: CrossRef may store given/family in either order ("Wei Zhang" with given="Wei" vs given="Zhang"). Match on the name *set*, not position, and note the ambiguity.
- Hyphenated Korean names: "Min-Yeong", "Min Yeong", "Minyeong" are the same person — normalize spacing/hyphens before comparing.
- Consortium / 50+-author papers: "first author" may be a collaboration name. Note this rather than forcing a single-author match.

**Layer 3 — Content Traceability** ← most important layer

This is where the skill's core value lies. The goal is not just "does this paper exist" but "does this paper actually contain the claim being attributed to it."

Before checking content, classify the claim depth:

- **Tier-1 existence/topic-level**: "Does this paper discuss X?", "Is this the paper about Y?", DOI/title/author/year sanity. Abstract verification is sufficient.
- **Tier-2 mechanism/implementation-level**: "How, where, or via what does X happen?" This includes heat-source location, current path, electrode/device configuration, material bulk vs surface mechanism, actuator/sensor role separation, and measurement conditions behind specific quantitative values. Abstract verification is not sufficient; full text is mandatory.

Fetch the abstract using this priority order:
1. CrossRef raw JSON: `https://api.crossref.org/works/{DOI}` — check the `abstract` field
2. Semantic Scholar: append `&fields=abstract` to your S2 DOI lookup
3. Open-access fallback: `https://api.unpaywall.org/v2/{DOI}?email={user_email}` — check `is_oa` and `oa_locations`. Unpaywall requires a real, valid email; ask the user for theirs once and reuse it. A placeholder address may be rejected or rate-limited.
4. arXiv fallback for preprints: `https://export.arxiv.org/api/query?id_list={arxiv_id}`
5. PubMed Central for life/bio papers: `https://www.ncbi.nlm.nih.gov/pmc/articles/{PMCID}/`

CrossRef abstracts are wrapped in JATS XML (`<jats:p>`, `<jats:italic>`, etc.). Strip these tags before quoting — the verbatim requirement means the abstract *text*, not the markup. An empty-string `abstract` field counts as absent, not as a fetched abstract; fall through to the next source.

For Tier-2 claims, also fetch full text before assigning support:
1. PubMed Central article HTML/XML when a PMCID exists
2. NCBI ID Converter when DOI maps to a PMCID but the article page is hard to scrape: `https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={DOI}&format=json` — returns the PMCID if one exists; use it to construct the PMC article URL. Europe PMC is a parallel full-text fallback: `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={title or DOI}&format=json` — covers PMC-deposited and European funder mandates.
3. Unpaywall OA locations, preferring `url_for_pdf` or `url_for_landing_page`
4. Publisher HTML or PDF from the DOI landing page
5. arXiv full text for preprints

When local source text is available, run the advisory checker to surface candidate evidence sentences and flags before writing the CONTENT verdict:

```
python3 checker.py --claim "[claim]" --abstract-file abstract.txt --full-text-file fulltext.txt
```

The checker is a pure evidence surfacer plus a tier hint. It NEVER emits an authoritative content ACCEPT or REJECT at ANY tier, and it NEVER asserts a claim is SUPPORTED. Its verdict is ALWAYS WARN (advisory). Soundness is therefore structural, not heuristic: because there is no ACCEPT in any code path, a content false-ACCEPT from the checker is impossible by construction, regardless of how the claim is classified or matched. The depth field (TIER_1/TIER_2) is only a hint telling you which text to read and which advisory wording to expect; a misclassification at worst gives a slightly less apt flag, never a wrong clearance.

- Tier-1 (topic/existence) hint: a topic match in the abstract returns content_status TOPIC-MATCH — agent must confirm, with verdict WARN, and surfaces the matched abstract sentence. The checker does NOT clear existence — it only sees text. Real existence/metadata/DOI verification is YOUR job via Layers 1, 2, and 4 (CrossRef, OpenAlex, DataCite, doi.org). Treat TOPIC-MATCH as "the abstract is on topic; now confirm the paper exists and read the sentence," not as a pass.
- Tier-2 (mechanism) hint: every result is WARN, annotated with one of CANDIDATE-SUPPORT (a clean candidate sentence binding the claim actor+action was found — confirm it verbatim), POSSIBLE-CONTRADICTION (a sentence negates the claim or assigns the action to a different actor — check it), PARTIAL (adjacent keywords only), NO-CANDIDATE (nothing found), ABSTRACT-LEVEL ONLY (full text not searched), or UNVERIFIABLE (no source).

The checker also returns the best candidate sentence verbatim in its evidence field. Every authoritative ACCEPT/WARN/REJECT in the skill OUTPUT is YOUR job: read the surfaced sentence and apply the verbatim-quote rule (INC1).

The checker is advisory at every tier. It does not decide support — it points you at the sentence to read. TOPIC-MATCH means: an on-topic abstract sentence was found; you assign the existence/topic call yourself after confirming the paper exists (two-source) and reading the sentence. CANDIDATE-SUPPORT means: a clean sentence was found; you assign SUPPORTED (full-text confirmed)/ACCEPT only after confirming a verbatim quote from that sentence actually binds the claimed actor, action, and any condition. POSSIBLE-CONTRADICTION means: a sentence negates the claim or attributes the action to a different actor; read it verbatim and assign CONTRADICTED/REJECT only if your verbatim read confirms it — do NOT auto-reject on the flag alone, and do NOT auto-accept by ignoring it. PARTIAL/NO-CANDIDATE/ABSTRACT-LEVEL ONLY/UNVERIFIABLE all stay WARN until you read source text that lets you make a stricter or supported call yourself. The verbatim quote you read always governs (INC1); the checker never overrides it and you never let a checker label substitute for reading the sentence.

After fetching, check: does the right source contain the specific claim being cited? The checker only ever flags WARN — every authoritative CONTENT call below is YOURS, made from the verbatim source text:

- Tier-1: checker returns TOPIC-MATCH and a sentence → confirm existence via two sources (Layer 1) and read the sentence; if the abstract explicitly contains the claim, write `CONTENT: SUPPORTED (abstract-level)` and quote it verbatim. The checker did not clear it — your two-source existence check plus verbatim read does.
- Tier-2: checker returns CANDIDATE-SUPPORT and a sentence → read the sentence; if a verbatim quote binds the mechanism (actor, action, and any condition), write `CONTENT: SUPPORTED (full-text confirmed)` and quote it; otherwise treat as PARTIAL and write WARN.
- Tier-2: checker returns POSSIBLE-CONTRADICTION and a sentence → read it; if it genuinely denies the claim or names a different actor, write `CONTENT: CONTRADICTED — do not use this citation` and quote it; if your read clears it, treat as PARTIAL or SUPPORTED per the quote.
- Any tier: checker returns PARTIAL / NO-CANDIDATE / ABSTRACT-LEVEL ONLY / UNVERIFIABLE → the checker found no confirmable support; default WARN, and write CONTENT only from what you can quote from the source text.
- Abstract is about the topic but doesn't make the specific Tier-1 claim → `CONTENT: PARTIAL — quote what it actually says`
- Tier-1: abstract not accessible after trying all 5 sources → `CONTENT: UNVERIFIABLE — no abstract accessible (Tier-1 ends here)`

The checker's own verdict is always WARN at every tier — it never delivers an authoritative content ACCEPT or REJECT on your behalf. A SUPPORTED content rating is something you write from a verbatim quote, never something the checker hands you.

**The rule that cannot be relaxed**: if you describe what a paper "shows" or "demonstrates" or "reports," you must quote directly or paraphrase only from the fetched source text at the required depth. Summarizing from memory is not permitted even if you feel confident. Abstracts prove topic direction, not implementation details.

For Tier-2 claims (mechanism/implementation), if neither the abstract nor any full-text source can be fetched after exhausting all Layer-3 fallbacks, the content verdict is `CONTENT: UNVERIFIABLE — no abstract or full text accessible`. Do not assign any support rating, partial or otherwise, on the basis of title or keyword match alone.

For Tier-2, keyword co-occurrence is not support. The quoted sentence(s) must bind the mechanism actors and relation: what component does the action, where it is located, what path/current/stimulus is used, and what role the material plays. If the quote says "LM layer served as a flexible Joule heater" and the claim says "the LCE bulk served as the Joule heater," that is `CONTRADICTED`, not partial support.

**Scope limit — know where this degrades**: many journals deposit no abstract in CrossRef or S2, and paywall full text everywhere else. This is common in materials science, polymer, and engineering venues (Smart Materials and Structures, Sensors and Actuators A, etc.). For Tier-1 claims, the content layer can legitimately end at `UNVERIFIABLE` when no abstract is openly available. For Tier-2 claims, a topic-matching abstract without full text ends at `ABSTRACT-LEVEL ONLY` — that is the skill working correctly, not failing. Existence, metadata, and DOI resolution still verify; only the content claim cannot. Tell the user plainly which source depth is missing rather than implying the citation is fully cleared.

**Layer 4 — DOI Resolution**

Fetch `https://doi.org/{DOI}`. Confirm the landing page matches the expected paper. A 403 (bot-blocked) from a URL slug containing the title and volume is not a dead link — note it as paywalled. A redirect to an unrelated page is a critical failure.

**Not every DOI is registered with CrossRef.** Before declaring a DOI dead, check the registration agency. arXiv preprints (`10.48550/arXiv.*`), Zenodo/figshare datasets, and many preprints are registered with **DataCite**, not CrossRef — they return 404 from `api.crossref.org` while being perfectly valid. If CrossRef 404s, try:
- DataCite: `https://api.datacite.org/dois/{DOI}`
- Or content negotiation: `https://doi.org/{DOI}` with `Accept: application/vnd.citationstyles.csl+json`

Only mark `DEAD` if the DOI fails to resolve at doi.org AND is absent from both CrossRef and DataCite. A DataCite-only DOI is valid — note the registrar rather than downgrading it.

**Layer 5 — Retraction**

Search `"{first author last name}" "{journal name}" retraction` and check the DOI landing page for retraction banners. For the CrossRef JSON structural check, inspect `message.title[0]` for a `"RETRACTED ARTICLE:"` or `"Retracted:"` prefix — treat this as the primary structural retraction signal, since `message.update-to` is frequently absent. Also inspect `message.assertion[]` for retraction notices. Check OpenAlex `is_retracted` as a cross-check (see Layer 1). Free-text search alone produces false negatives for recent or poorly-indexed retractions — treat a clean search as "no retraction found," not "definitely not retracted." A retracted paper must not be used as a primary source.

---

## Output Format

**Quick Screen**: one line per reference (see above).

**Full Audit**: one card per paper, then a summary table.

```
REFERENCE AUDIT
────────────────────────────────────────────────
Paper:   [Title from live source — not from memory]
DOI:     [DOI] — [✓ Resolves | ✗ Dead | ✗ Wrong paper | ⚠ Paywalled-403]
Authors: [Full list from CrossRef/S2]
Year:    [Year] — Source: CrossRef | S2 | arXiv
Journal: [Full name]

EXISTENCE:  ✓ Confirmed (sources) | ⚠ Single-source | ✗ Not found
METADATA:   ✓ Consistent | ⚠ Discrepancy: [field: value-A vs value-B]
CONTENT:    ✓ Supported (full-text confirmed) — "[verbatim full-text excerpt]"
            ✓ Supported (abstract-level) — "[verbatim abstract excerpt]"
            ⚠ Abstract-level only — mechanism claim needs full text
            ⚠ Partial — source says: "[what it actually says]"
            ✗ Unsupported | ✗ Contradicted | — Unverifiable (tried required sources)
RETRACTION: ✓ None found | ✗ Retracted

VERDICT: ACCEPT | WARN | REJECT
Reason: [one sentence — what's missing or wrong]
────────────────────────────────────────────────
```

CONTENT field must show either a verbatim excerpt or an explicit warning/unverifiable state — never a summary written from memory.

**ACCEPT**: two-source confirmed, DOI resolves to right paper, content supported at the required depth — and no retraction. The checker never grants this at any tier; you assign it yourself. For Tier-1 you must have a two-source existence confirmation plus a verbatim abstract quote of the topic claim (the checker's TOPIC-MATCH only points you at the sentence). For Tier-2 you must have personally confirmed a verbatim full-text quote that binds the mechanism (the checker only surfaces a CANDIDATE-SUPPORT sentence).
**WARN**: solvable issue — single source, partial content match, abstract inaccessible after trying all fallbacks, or any claim where the checker returned a flag (TOPIC-MATCH, CANDIDATE-SUPPORT, POSSIBLE-CONTRADICTION, PARTIAL, NO-CANDIDATE, ABSTRACT-LEVEL ONLY, or UNVERIFIABLE) and you have not yet confirmed by verbatim read. Safe to use only if user verifies the flagged item.
**REJECT**: DOI dead or resolves to wrong paper, paper not found anywhere, content contradicted (verbatim-read confirmed), or retraction confirmed. A Tier-2 REJECT (CONTRADICTED/unsupported) must be backed by your verbatim read of the contradicting or absent evidence — a POSSIBLE-CONTRADICTION flag alone is WARN, not REJECT, until you confirm it.

Summary table after all cards:

```
SUMMARY
────────────────────────────────────────────────
1. Smith et al. (2021)  — ACCEPT
2. Kim & Park (2019)    — WARN (abstract unverifiable; try PMC or institutional access)
3. Zhang (2023)         — REJECT (DOI resolves to different paper)
────────────────────────────────────────────────
X / Y verified.  Z need attention.
```

---

## Anti-Hallucination Rules

- Never recall a DOI from memory — fetch from CrossRef or S2.
- Never describe paper content without fetched source text at the required claim depth to quote from.
- Never verify mechanism/implementation claims from the abstract alone. Heat source, electrode/device configuration, current path, quantitative measurement conditions, and similar how/where/via-what claims require full text; if full text is unavailable, mark `ABSTRACT-LEVEL ONLY`, not supported.
- Never treat adjacent keywords as content support. For mechanism claims, the quote must bind the claimed actors and causal relation, not merely mention the same material, stimulus, or property.
- Never fill in missing metadata by guessing or pattern-matching.
- If two sources disagree, show both — do not choose silently.
- If the source text required for the claim depth is inaccessible after all fallbacks, use `UNVERIFIABLE` or `ABSTRACT-LEVEL ONLY` as specified above — do not substitute a description from memory.
- The checker is advisory at EVERY tier: it surfaces a matched or candidate or contradicting sentence and a flag, but it never asserts any claim is SUPPORTED and never returns an authoritative ACCEPT or REJECT. Its verdict is always WARN. Treat every checker result — TOPIC-MATCH included — as WARN until your own verbatim quote (INC1), plus two-source existence for Tier-1, decides the call. A TOPIC-MATCH flag does not clear existence; a POSSIBLE-CONTRADICTION flag does not by itself reject — read the surfaced sentence first.

---

## Edge Cases

**Preprint vs. published**: record both DOIs; prefer published for citation; note if title changed between versions.

**Author name variants**: "J. Smith" vs "John Smith" — flag but do not merge; let user confirm.

**Conference proceedings**: volume/pages often absent from CrossRef; mark `[NOT IN SOURCE]`, not guessed.

**S2 rate limiting**: wait 2s and retry once; if still failing, use CrossRef as primary and note single-source limitation.
