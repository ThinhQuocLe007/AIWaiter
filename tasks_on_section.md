# Thesis v3 — Issues & Improvement Tasks (Agent Focus)
*Deep check: Chapters 4 & 5 + cross-reference with evaluation logs*
*Scope: AI agent only. Navigation/robot excluded. Numbers are currently from qwen2.5:7b; will be updated to 14b later.*

---

# A. CRITICAL — Data Integrity

## A1. VERBALISATION NUMBERS ARE STALE (Ch5 §5.4.3)

**Thesis** (from old Jul 26 run): fully verbalised **57.6%**, verbalisation rate **72.5%**

**Latest eval** (Jul 31, same 7B model, code improved): fully verbalised **92%**, verbalisation **92%**

**Gap: +34 points** from code fixes between Jul 26 and Jul 31. The thesis uses stale data no matter which model.

**Action:** Re-run N=5 on latest code (whether 7B or 14B), update Ch5 §5.4.3 prose, Table 5.16, scorecard, and Ch6 limitations text. The "this property is not met" verdict likely flips.

**Eval results history (all on 7B):**

| Date | verbalisation | fully_verbalised | strict_verb | strict_full |
|------|:-:|:-:|:-:|:-:|
| Jul 27 17:56 | 0.80 | 0.80 | 0.80 | 0.80 |
| Jul 27 18:00 | 0.72 | 0.68 | 0.60 | 0.52 |
| Jul 27 18:31 | 0.80 | 0.76 | 0.72 | 0.68 |
| **Jul 31 21:42** | **0.92** | **0.92** | 0.84 | 0.76 |
| **Jul 31 21:55** | **0.92** | **0.92** | 0.84 | 0.76 |

The corrected scoring rule was implemented ~Jul 27; code improvements continued through Jul 31.

---

## A2. MODEL CLARITY (Ch5 lines 16-17)

Current text says "The language model is Qwen2.5 14B Instruct... The evaluation reported in this chapter was carried out with qwen2.5:14b-instruct." — contradicts actual eval files (7B). 

**Action:** Add a clear upfront note: "Evaluated on qwen2.5:7b-instruct pending re-run on the deployment 14B model. Figures are a lower bound on what the deployment model would produce. The trained classifier, deterministic validator, and retrieval indices are independent of model choice."

All LLM-dependent numbers (latency, verbalisation, E2E) will be updated after 14B re-run.

---

## A3. N=5 PROTOCOL NOT MET FOR KEY EXPERIMENTS

The thesis §5.2.1 claims N=5 for stochastic experiments. But:
- Verbalisation (latest): single runs only (`runs: 1` in JSON)
- Validator ablation: single run
- Out-of-menu: single run
- Delegate: single run  
- Retrieval rewrite: single run

Only latency and the stale verbalisation run meet N=5. All need N=5 re-runs before final numbers.

---

# B. CRITICAL — Chapter 4 Structural Issues

## B1. MISSING SECTIONS 4.7.3 AND 4.7.4

Ch4 ends at `### 4.7.2 The Dispatcher`, then jumps to `## 4.8 Web Interfaces`. But line 420 references **"Section 4.7.4"**: "which is the seam where the kitchen's work becomes the robot's (Section 4.7.4)."

**Neither 4.7.3 nor 4.7.4 exists.** These likely cover fleet management (task lifecycle, robot assignment). Either write the sections or remove the cross-reference.

## B2. BROKEN CROSS-REFERENCE TO NONEXISTENT §5.6.2

Ch4 line 303: "Section 5.6.2 of Chapter 5 reports it as such." Chapter 5 ends at 5.5.2 — no 5.6 exists. Fix the reference.

## B3. DUPLICATE SUBSECTION NUMBER — TWO "4.6.3"s

- `### 4.6.3 Relevance Gatekeeper` (line 334)
- `### 4.6.3 Result Rephrasing` (line 358)

Second should be **4.6.4**.

## B4. GATEKEEPER THRESHOLD — 0.35 vs 0.25

| Ch4 line 336 | "cosine similarity reaches **0.35**" |
| Ch4 line 351 (Table 4.13) | "At least **0.35**" |
| Ch5 line 335 | "against a threshold of **0.25**" |

**0.25 is the correct value.** Ch4 lines 339-340 explain why: answerable queries score 0.27–0.65, unanswerable 0.29–0.32, and "the threshold sits below both." A threshold of 0.35 would sit ABOVE 0.27 and 0.29, contradicting the prose. Change all Ch4 references to **0.25**.

Also: Ch4 line 336 says "top FAISS result" (top-1) but Table 4.13 says "top-3 cosine similarity" — inconsistent scope.

## B5. MISSING RRF EQUATION

Ch4 line 331: "Each list contributes to a document the quantity" — the RRF equation is blank. Fill from the code or standard formula.

## B6. DUPLICATED DRAFTING TEXT

Ch4 line 262: "Table 4.10 sets out the five subtypes, one per kind of outcome a turn can reach. **which is what makes the model safe to call on it. Table 4.10 sets out the five.**" — Editing artifact. Fix.

## B7. CHAPTER 4 §4.5.3 — "Two Clarifications" PARAGRAPH CONFUSION

Ch4 line 176 starts a long paragraph: "The second choice is where the one thing the design cannot establish is absorbed..." It's dense and hard to follow. The sentence "Nothing here can supply that figure. What the design can do is give the model less to get wrong." could be clearer as a separate short paragraph.

---

# C. CRITICAL — Chapter 5 Agent-Section Issues

## C1. "SIX CONVERSATIONS" vs SEVEN ROWS (Table 5.20)

Table 5.20 title: "The six conversations" — but table has **seven** rows (G.1 through G.7). Lines 361, 364 correctly reference seven. Fix title.

## C2. WRONG APPENDIX REFERENCE

Line 253: "Appendix **G.3** shows a live turn and the clarification the customer hears" — about ambiguous dish name. G.3 = QS-003 (multi-intent). Should be **G.5** (QS-005, ambiguous dish).

## C3. UNDEFINED "N10" REFERENCE

Line 400 (Table 5.21): "Multi-intent verbalisation completeness | not targeted | **see N10** | partially met"
**N10** is not defined anywhere. Remove or define.

## C4. "NOT TARGETED / PARTIALLY MET" CONTRADICTION

Same row: Target says "not targeted" but Status says "partially met" — contradictory. If it wasn't targeted, it can't be partially met.

## C5. REFERENCE TO NONEXISTENT §5.5.3

Line 268: "§5.5.3 records what that leaves open." Chapter 5 has no 5.5.3 (ends at 5.5.2).

## C6. MISSING SPACES IN SECTION REFERENCES

Lines 191: "section5.4.3", "section5.4.5", "section5.4.6" — need spaces: "Section 5.4.3" etc.

## C7. TABLE 5.10 — EMPTY QUANTITATIVE RESULT COLUMN

All 5 rows have blank cells. Fill or remove column.

## C8. TABLE 5.21 OBJ 4 — EMPTY TARGET CELL

Knowledge retrieval target is blank. Fill from Ch1: "R@5 ≥ 0.70; top-5 hit ≥ 90%"

## C9. EMPTY LATEX VALUES (Chapter 5)

Lines 115-116, 167-168 have empty numeric values from lost LaTeX formulas. Fill from raw measurement data or the .docx.

## C10. GARBLED FIGURE CAPTION

Line 174: "FIGURE .dă.da.wd.awd.ăd" — corrupted placeholder.

---

# D. CRITICAL — Chapter 6 vs Chapter 5 Scorecard

| Metric | Ch5 Table 5.21 | Ch6 Conclusion table | Correct source |
|--------|:---:|:---:|:---:|
| Intent accuracy | **95.3%** (142/149) | **94.0%** (140/149) | Ch5 matches eval |
| Router latency vs LLM | **9.0 ms** vs 217.1 ms | **8 ms** vs 195 ms | Ch5 matches eval |
| Agent turn latency p50 | **1.61 s** | **1.74 s** | Ch5 matches eval |
| E2E ordering | 29/35 runs, **7 scenarios** | "**5/6** conversations pass" | Ch5 (7 scenarios) |
| Knowledge retrieval hit rate | 0.840 (prose) | **0.958** | **0.840** matches eval |
| Knowledge retrieval target | empty | **", "** (bare comma) | Fill from Ch1 |

**Action:** Rebuild Ch6 table from Ch5 numbers. Pick ONE consistent set.

---

# E. CRITICAL — Chapter 6 Placeholder

**Line 11: "Table đâu ?"** — Vietnamese for "Where is the table?" Replace with actual results summary table.

---

# F. HIGH — Cross-Chapter Consistency

## F1. Chapter 1 section numbering broken
- "Motivation" → should be **1.1**
- "Objectives" → should be **1.3**
- Fix numbering throughout

## F2. Chapter 1 §1.5 inaccurate
Says "Chapter 5: Presents the implementation process" but Ch5 is purely experimental results. Implementation is Ch3-Ch4.

## F3. Lists of Figures/Tables — empty
Both files contain only headings. Populate after all edits are final.

## F4. References — broken URLs
Many have `[Online]. Available: .` with empty URLs. Restore from .docx.

## F5. Garbled bold formatting
Multiple instances: "EDU**CATION", "MECHANICAL** ENGINEERING", "GRADUATION** THESIS" — Word mid-word bold splits. Clean up.

## F6. Acknowledgment uses "I" but signed by 3 students
Change to "We" throughout.

---

# G. MEDIUM — Appendix G

## G1. Duplicate descriptions (G.3 and G.4)
G.3 and G.4 have identical opening paragraphs. G.4 should describe "changing your mind mid-order", not repeat the multi-intent text from G.3.

## G2. G.5 transcript incomplete
Description says "Twelve turns" but only 3 are shown. Restore the remaining turns.

---

# H. COMPRESSION (Agent-relevant sections only)

## Ch2 — Related Work (~68K chars)
| Section | Savings |
|---------|:---:|
| 2.1.3 Restaurant Management Software | 0.5 pg |
| 2.3 intro (3 verbose framing paragraphs) | 0.75 pg |
| 2.3.1 VAD latency discussion | 0.5 pg |
| 2.3.2 STT prose after table | 0.5 pg |
| 2.4.2 Agent architecture descriptions | 0.5 pg |
| 2.5.4 Beyond RAG | 0.5 pg |
| 2.6 Web System prose (tables already convey info) | 1.0 pg |
| **Ch2 total:** | **~4 pg** |

## Ch4 — AI & Backend (~78K chars)
| 4.2 Design Challenges (restates 4.1) | 0.75 pg |
| 4.5.4 Validator walkthrough (verbose) | 0.75 pg |
| 4.5.5 State management (prose + table) | 0.5 pg |
| 4.6 Retrieval (query rewriting + gatekeeper verbose) | 0.5 pg |
| **Ch4 total:** | **~2.5 pg** |

## Ch5 — Experimental Results (~72K chars)
| 5.1 Hardware (duplicates Ch3-Ch4) | 0.5 pg |
| 5.4.1 Ablation analysis (McNemar, failure profiles) | 0.5 pg |
| 5.4.4 Fusion ablation (table already shows result) | 0.5 pg |
| **Ch5 total:** | **~1.5 pg** |

**Grand total: ~8 pages compressible from agent sections alone.**

---

# I. PRIORITY ORDER

| # | Task | Impact |
|:-:|------|:---:|
| 1 | Re-run verbalisation N=5 on latest code, update §5.4.3 + Table 5.16 + scorecard | Flips verdict |
| 2 | Fix Ch4 missing §4.7.3/4.7.4 | Broken structure |
| 3 | Fix gatekeeper threshold 0.35→0.25 across Ch4 | Wrong numbers |
| 4 | Reconcile Ch6 scorecard with Ch5 | Contradictory claims |
| 5 | Fix Ch4 duplicate 4.6.3 + broken §5.6.2 reference | Broken structure |
| 6 | Fix Ch1 section numbering + §1.5 inaccuracy | Formatting |
| 7 | Fix Ch5 C1–C10 (table titles, wrong refs, N10, empty cells) | Formatting |
| 8 | Replace "Table đâu ?" in Ch6 | Embarrassing |
| 9 | Fix Appendix G errors | Content |
| 10 | Apply compression | Page count |
| 11 | Populate list of figures/tables (last) | Formatting |
