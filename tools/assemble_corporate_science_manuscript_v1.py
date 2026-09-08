from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("manuscript/corporate_science_entry_v1")
INTRO = ROOT / "INTRO_THEORY_DRAFT.md"
METHODS = ROOT / "METHODS_DRAFT.md"
RESULTS = ROOT / "RESULTS_DISCUSSION_DRAFT.md"
OUT = ROOT / "COMPLETE_MANUSCRIPT_DRAFT.md"

for p in [INTRO, METHODS, RESULTS]:
    if not p.exists():
        raise FileNotFoundError(p)

intro = INTRO.read_text(encoding="utf-8")
methods = METHODS.read_text(encoding="utf-8")
results = RESULTS.read_text(encoding="utf-8")

# ----------------------------
# Introduction/theory body + references
# ----------------------------
if "\n## References\n" in intro:
    intro_body, intro_refs = intro.split("\n## References\n", 1)
else:
    intro_body, intro_refs = intro, ""

# Remove the source draft's title; the complete manuscript uses the reviewer-safe working title below.
intro_lines = intro_body.splitlines()
if intro_lines and intro_lines[0].startswith("# "):
    intro_lines = intro_lines[1:]
intro_body = "\n".join(intro_lines).strip()

# ----------------------------
# Methods body
# ----------------------------
if "\n# Methods\n" in methods:
    _, methods_body = methods.split("\n# Methods\n", 1)
else:
    methods_body = methods
# Internal adaptation/audit notes are not part of the clean manuscript.
methods_body = methods_body.split("\n# Methods audit notes for later journal adaptation\n", 1)[0].strip()

# ----------------------------
# Results + discussion body
# ----------------------------
if "\n# Results\n" not in results or "\n# Discussion\n" not in results:
    raise RuntimeError("Expected Results/Discussion headings were not found")
_, rd = results.split("\n# Results\n", 1)
results_body, discussion_tail = rd.split("\n# Discussion\n", 1)

if "\n# References used for Discussion grounding\n" in discussion_tail:
    discussion_body, discussion_refs_tail = discussion_tail.split("\n# References used for Discussion grounding\n", 1)
else:
    discussion_body, discussion_refs_tail = discussion_tail, ""

if "\n# Manuscript claim boundary\n" in discussion_refs_tail:
    discussion_refs, _ = discussion_refs_tail.split("\n# Manuscript claim boundary\n", 1)
else:
    discussion_refs = discussion_refs_tail

# Editorial calibration identified by the structural audit. These changes alter wording only.
results_body = results_body.replace(
    "the persistence advantage associated with earlier entry",
    "the early-entry–persistence relationship",
)
discussion_body = discussion_body.replace(
    "the persistence advantage associated with earlier entry",
    "the early-entry–persistence relationship",
)

results_body = results_body.strip()
discussion_body = discussion_body.strip()

# ----------------------------
# Reference merge/deduplication
# ----------------------------
def split_reference_entries(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    entries: list[str] = []
    # Discussion references are markdown bullets; intro references are paragraph separated.
    bullet_lines = [ln.strip()[2:].strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
    if bullet_lines:
        entries.extend([x for x in bullet_lines if x])
        # Preserve any non-bullet paragraph entries too.
        nonbul = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("- ")).strip()
        if nonbul:
            entries.extend([b.strip().replace("\n", " ") for b in re.split(r"\n\s*\n", nonbul) if b.strip()])
    else:
        entries.extend([b.strip().replace("\n", " ") for b in re.split(r"\n\s*\n", text) if b.strip()])
    return entries


def ref_key(ref: str) -> str:
    doi = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", ref, flags=re.I)
    if doi:
        return "doi:" + doi.group(0).rstrip(".);,").lower()
    normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", ref.lower())).strip()
    return normalized[:160]

refs: list[str] = []
seen: set[str] = set()
for ref in split_reference_entries(intro_refs) + split_reference_entries(discussion_refs):
    key = ref_key(ref)
    if key and key not in seen:
        seen.add(key)
        refs.append(ref.lstrip("- ").strip())

references = "\n\n".join(refs)

# ----------------------------
# Locked, calibrated abstract
# ----------------------------
abstract = """Firms increasingly participate directly in emerging scientific domains, yet it is unclear whether entering earlier produces a persistent corporate scientific advantage. We examine relative corporate entry timing at the firm–scientific-topic level and distinguish the effects of early entry from the role of pre-entry international scientific collaboration networks. The frozen primary panel contains 171 firm-topic entry episodes across 54 scientific topics and 21 linked firms; 65 episodes enter within two years of the first linked corporate entrant and 106 enter later. We combine overlap weighting on pre-entry firm characteristics with absorbed fixed effects, multiple cluster-robust inference procedures, and a prespecified sensitivity grid of alternative topic-emergence and early-entry definitions. Earlier relative entry is not associated with higher subsequent topic output or greater three-year persistence, while the primary citation-impact contrast lacks sufficient within-topic support and sensitivity-only estimates are near zero. Pre-entry international network diversity does not predict earlier entry. The interaction between early entry and pre-entry network diversity is positive across most frozen design definitions and remains positive in all leave-one-firm-out refits, but its statistical support is sensitive to small-cluster inference. The findings therefore do not support an automatic first-mover advantage in observable corporate scientific production. Instead, they point toward a capability-contingent interpretation in which early entry may create an opportunity whose persistence depends partly on the external knowledge architecture the firm brings to the domain. The results are associational and do not identify a causal effect of entry timing."""

front = f"""# When Early Entry Is Not Enough: Corporate Scientific Entry, Persistence, and International Knowledge Networks

**Authors:** [Author names]  
**Affiliations:** [Affiliations]  
**Corresponding author:** [Corresponding author details]

## Abstract

{abstract}

**Keywords:** corporate science; entry timing; first-mover advantage; absorptive capacity; international collaboration; scientific networks; emerging technologies; persistence

"""

back = """

## Data and code availability

The analysis was executed against a frozen, checksum-verified GMS research release derived from public SEC issuer data and OpenAlex scientific metadata. Version-controlled analysis code, design-freeze specifications, checksums, and immutable research checkpoints are retained in the project repository and research data lake. Any public-release package should expose only materials permitted by the underlying source licenses and project data-release policy.

## Funding

[Funding statement]

## Conflict of interest

[Conflict-of-interest statement]

## Author contributions

[CRediT author-contribution statement]
"""

master = (
    front
    + intro_body
    + "\n\n# Methods\n\n"
    + methods_body
    + "\n\n# Results\n\n"
    + results_body
    + "\n\n# Discussion\n\n"
    + discussion_body
    + "\n\n# References\n\n"
    + references
    + back
)

# Final assembly QA: prohibited overclaims must not occur.
prohibited = [
    "early entry causes higher persistence",
    "H5 is confirmed",
    "H5 is robustly significant",
    "H3 is supported in the primary model",
    "H3 is rejected in the primary model",
]
for phrase in prohibited:
    if phrase.lower() in master.lower():
        raise RuntimeError(f"Prohibited manuscript claim present: {phrase}")

# Required locked markers.
required = [
    "171 firm-topic",
    "54 scientific topics",
    "21 firms",
    "65",
    "106",
    "p2_100",
    "CRV3",
    "9,999",
    "not estimable",
    "qualified directional support",
]
missing = [x for x in required if x.lower() not in master.lower()]
if missing:
    raise RuntimeError(f"Assembly missing required locked markers: {missing}")

OUT.write_text(master.strip() + "\n", encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
