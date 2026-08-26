<div align="center">

<img src=".github/assets/groundcheck-mark-512.png" alt="groundcheck mark" width="96">

</div>

# groundcheck

**Verification skills for academic research — every claim grounded in fetched evidence, never recalled from memory.**

AI agent skills for researchers who can't afford a hallucinated citation, a misread figure, or an invented statistic. Install individually or all at once.

Each skill targets a gap not covered by existing research software. Skills were checked on a handful of real-paper test cases during development (illustrative, not a controlled benchmark — see [Evaluation notes](#evaluation-notes)).

---

## Install

```bash
# individual skill
npx skills add Moonweave-Research/groundcheck@ref-verify -g

# all skills (once available)
npx skills add Moonweave-Research/groundcheck -g
```

Works with **Claude Code, Cursor, Codex**, and any `npx skills` compatible agent.

---

## Skills

### ref-verify — Citation hallucination prevention
**Status: stable (v1.0.0)**

Prevents AI agents from citing papers with wrong DOIs, wrong authors, wrong year, or fabricated content. Every citation is verified live against CrossRef, Semantic Scholar, and PubMed. Every content claim is traced to a verbatim-fetched abstract — never recalled from training data.

```bash
npx skills add Moonweave-Research/groundcheck@ref-verify -g
```

**Real catches during testing:**
- Abstract content described by AI that doesn't appear in the actual CrossRef record
- DOI resolving to a completely different paper (different authors, different year)
- "500% strain" in an abstract that referred to a measurement condition, not an actuation result

→ [README](ref-verify/SKILL.md) · [Standalone repo](https://github.com/Moonweave-Research/ref-verify)

---

### arxiv-monitor — Daily arXiv briefing
**Status: stable (v1.0.0)**

Scheduled monitoring of new arXiv papers by keyword and author watchlist. LLM-based relevance scoring (1-5 tiers). Routable output to Slack, Obsidian, Telegram, or file. Built for Claude Code Routines. Auto-detects low-arXiv-coverage domains and falls back to Semantic Scholar.

**Why build this:** Scholar Inbox handles passive email digests well. The gap is agent-native monitoring with custom filtering and routing that connects directly to your research workflow.

```bash
npx skills add Moonweave-Research/groundcheck@arxiv-monitor -g
```

→ [SKILL.md](arxiv-monitor/SKILL.md)

---

### figure-verifier — Text-vs-figure claim verification
**Status: beta (v1.0.0)** — workflow and structured verdicts are solid; the figure-*image* reading path (VLM precision on dense plots) is resolution-dependent and under-tested. Treat readings as approximate.

Reads numerical values from scientific figures, then cross-checks them against quantitative claims in the paper's text. Flags discrepancies, wrong figure pointers (value cited in the wrong figure number), and characterizes whether a figure is quantitative or photographic before reading.

**Why build this:** WebPlotDigitizer and PlotPick extract data from figures. No existing tool — anywhere — verifies whether a paper's stated results are actually supported by its own figures. This is the figure equivalent of what ref-verify does for citations.

```bash
npx skills add Moonweave-Research/groundcheck@figure-verifier -g
```

→ [SKILL.md](figure-verifier/SKILL.md)

---

### contradiction-finder — Cross-paper conflict detection
**Status: stable (v1.0.0)**

Takes a set of papers (by DOI or search query), extracts atomic claims from abstracts, compares them pairwise, and surfaces conflicts (DIRECT / QUANTITATIVE / SCOPE) with verbatim evidence. Its core discipline: it does not infer a contradiction from a claim a paper's abstract doesn't actually make.

**Why build this:** Scite detects contradictions at the citation-graph level but only reactively (you supply the claim). Elicit shows divergent values but doesn't call them out as conflicts. No tool proactively maps contradictions from a paper set.

```bash
npx skills add Moonweave-Research/groundcheck@contradiction-finder -g
```

→ [SKILL.md](contradiction-finder/SKILL.md)

---

### nrf-grant — NRF 연구계획서 작성
**Status: stable (v1.0.0)**

한국연구재단(NRF) 연구계획서 작성 전용 스킬. 필요성·연구내용·활용방안 섹션 구조, 우수성·필요성·실현가능성·활용방안 4대 심사기준 정렬, 한국어 학술 문체, 과제 유형별(신진/중견/선도연구센터/BK21) 특이사항 반영.

**Why build this:** NSF/NIH용 AI 도구는 포화 상태. NRF 형식을 지원하는 도구는 전 세계에 없음.

```bash
npx skills add Moonweave-Research/groundcheck@nrf-grant -g
```

→ [SKILL.md](nrf-grant/SKILL.md)

---

## Design principles

All skills in this collection follow the same rules:

1. **Live verification over memory recall** — claims are grounded in fetched data, not training recall
2. **Explicit uncertainty** — if something can't be verified, it says so instead of guessing
3. **Narrow scope** — each skill does one thing well; no feature creep
4. **Evidence in output** — every verdict includes the source and evidence that produced it

---

## Evaluation notes

Honesty about what the testing does and doesn't show:

- Each skill was checked against a no-skill baseline on **3 illustrative test cases** during development. This is **not a controlled benchmark** — it's n=1 per case, and run-to-run variance is real (contradiction-finder produced opposite verdicts on two runs of the same baseline).
- The measured advantage is mostly **consistency and structured output** — the skill reliably applies the same discipline (verbatim sourcing, explicit uncertainty, conflict taxonomy) where an unaided model is hit-or-miss. There are some genuine capability catches (e.g. ref-verify flagging abstract content an unaided model embellished), but the suite's main value is reproducible discipline, not catching errors the base model never could.
- **figure-verifier's image-reading path is the least-proven.** It has been validated end-to-end once (downloaded an arXiv figure PNG, read values off the pixels, with an anchoring guard against reading the caption) but figure-image precision is inherently approximate and resolution-dependent. Treat readings as approximate; low-resolution or cluttered plots should return UNREADABLE.
- **Content verification degrades to UNVERIFIABLE where abstracts aren't openly deposited** — common in materials/polymer/engineering journals. The skills report this honestly rather than guessing, but it means the content layer is weakest in exactly those fields.

### Validated paths (single-run, post-hardening)

After a review pass, four specific paths were each exercised once and behaved correctly:

- arXiv/DataCite DOIs (`10.48550/*`) are not falsely flagged DEAD when CrossRef 404s (DataCite fallback works)
- figure-verifier reads an actual figure image and fills a proof-of-vision line, rather than echoing the caption
- abstract-absent papers (e.g. *Smart Materials and Structures*) return UNVERIFIABLE honestly while existence/metadata/DOI still verify
- a same-material-system mechanism conflict is classified DIRECT, not escaped to SCOPE — and different-system pairs are not over-flagged

These are n=1 confirmations that the paths work, not a statistical benchmark. If you want a defensible comparison for your own use, re-run with skills uninstalled for the baseline and ≥3 runs per case, scoring on outcome rather than output format.

---

## Related

- [Moonweave-Research/ref-verify](https://github.com/Moonweave-Research/ref-verify) — standalone repo for ref-verify (v1.0.0, stable)
- [Moonweave-Systems/decision-kernel](https://github.com/Moonweave-Systems/decision-kernel) — evidence-gated decisions and drift/done checks for coding agents
