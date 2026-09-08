from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("manuscript/corporate_science_entry_v1")
MANUSCRIPT = ROOT / "TECHNOVATION_MANUSCRIPT_DRAFT.md"
FIRM = ROOT / "TECHNOVATION_FIRM_COMPOSITION.csv"
INDUSTRY = ROOT / "TECHNOVATION_INDUSTRY_COMPOSITION.csv"
REF_AUDIT = ROOT / "REFERENCE_DOI_AUDIT.md"

text = MANUSCRIPT.read_text(encoding="utf-8")

def words(s: str) -> list[str]:
    # Count human-readable word tokens while ignoring Markdown punctuation.
    return re.findall(r"\b[\w’'-]+\b", s, flags=re.UNICODE)

def between(s: str, start: str, end: str) -> str:
    a = s.index(start) + len(start)
    b = s.index(end, a)
    return s[a:b]

abstract = between(text, "## Abstract", "**Keywords:**")
kw_line = re.search(r"\*\*Keywords:\*\*\s*(.+)", text)
if not kw_line:
    raise RuntimeError("Keywords line not found")
keywords = [x.strip() for x in kw_line.group(1).split(";") if x.strip()]

main_start = text.index("## 1. Introduction")
main_end = text.index("## Data and code availability")
main_text = text[main_start:main_end]
pre_refs = text[: text.index("## References")]
refs = text[text.index("## References"):]

reference_entries = [p.strip() for p in re.split(r"\n\s*\n", refs)[1:] if p.strip()]
doi_matches = re.findall(r"https://doi\.org/([^\s]+)", refs, flags=re.I)

admin_placeholders = sorted(set(re.findall(r"\[[^\]\n]+\]", text)))
# Figure-location placeholders are intentional manuscript-production markers, not admin blockers.
admin_placeholders = [p for p in admin_placeholders if not p.lower().startswith("[figure ")]

prohibited = [
    "early entry causes higher persistence",
    "h5 is confirmed",
    "h5 is robustly significant",
    "h3 is supported in the primary model",
    "h3 is rejected in the primary model",
    "selecting a sensitivity design because it produces a smaller p-value",
]
prohibited_hits = [p for p in prohibited if p in text.lower()]

required_phrases = [
    "sample-relative",
    "associational rather than causal",
    "qualified directional support",
    "47.4%",
    "21.1%",
    "topic CRV3",
    "9,999",
]
missing_required = [p for p in required_phrases if p.lower() not in text.lower()]

checks = {
    "manuscript_exists": MANUSCRIPT.exists(),
    "firm_composition_exists": FIRM.exists(),
    "industry_composition_exists": INDUSTRY.exists(),
    "reference_audit_exists": REF_AUDIT.exists(),
    "abstract_150_250": 150 <= len(words(abstract)) <= 250,
    "keywords_max_6": len(keywords) <= 6,
    "main_text_5000_10000": 5000 <= len(words(main_text)) <= 10000,
    "reference_entries_17": len(reference_entries) == 17,
    "doi_entries_17": len(doi_matches) == 17,
    "no_prohibited_claims": len(prohibited_hits) == 0,
    "required_transparency_language_present": len(missing_required) == 0,
}

scientific_gate = all([
    checks["firm_composition_exists"],
    checks["industry_composition_exists"],
    checks["reference_audit_exists"],
    checks["reference_entries_17"],
    checks["doi_entries_17"],
    checks["no_prohibited_claims"],
    checks["required_transparency_language_present"],
])
journal_gate = all([
    checks["abstract_150_250"],
    checks["keywords_max_6"],
    checks["main_text_5000_10000"],
])
admin_gate = len(admin_placeholders) == 0

status = (
    "READY_FOR_SUBMISSION_ASSEMBLY_ADMIN_METADATA_REQUIRED"
    if scientific_gate and journal_gate and not admin_gate
    else "READY_FOR_SUBMISSION_ASSEMBLY"
    if scientific_gate and journal_gate and admin_gate
    else "REVISION_REQUIRED"
)

report = {
    "status": status,
    "manuscript_blob_context": "Technovation manuscript v2 after sample-transparency patch",
    "counts": {
        "abstract_words": len(words(abstract)),
        "keywords": len(keywords),
        "main_text_words_intro_through_conclusion": len(words(main_text)),
        "words_before_references_including_admin_sections": len(words(pre_refs)),
        "reference_entries": len(reference_entries),
        "doi_entries": len(doi_matches),
        "admin_placeholders": len(admin_placeholders),
    },
    "keywords": keywords,
    "admin_placeholders": admin_placeholders,
    "prohibited_claim_hits": prohibited_hits,
    "missing_required_transparency_language": missing_required,
    "checks": checks,
    "scientific_gate": scientific_gate,
    "journal_format_gate": journal_gate,
    "admin_gate": admin_gate,
    "irreducible_scientific_risks": [
        "The corporate adoption frontier is relative to the linked sample rather than population-complete.",
        "The frozen primary panel contains only 21 firms.",
        "Banking/depository institutions account for 47.4% of primary episodes; the largest firm accounts for 21.1%.",
        "H5 is directionally stable but inference-sensitive under CRV3 and firm wild-bootstrap inference.",
        "Entry timing remains endogenous; estimates are associational, not causal.",
        "Publication-based entry is a proxy for observable corporate scientific production, not private R&D awareness or investment.",
        "H3 is not estimable in the frozen primary design because within-topic support is insufficient.",
    ],
}

(ROOT / "FINAL_TECHNOVATION_QA.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

md = []
md.append("# Final Technovation Hostile-Reviewer / Submission Audit — V2")
md.append("")
md.append(f"**Automated status:** **{status}**")
md.append("")
md.append("This audit is run on the revised Technovation manuscript after the sample-composition, methods-citation, DOI, and keyword corrections. It does not reopen or re-estimate the locked empirical analysis.")
md.append("")
md.append("## Journal-format QA")
md.append("")
md.append(f"- Abstract: **{len(words(abstract))} words** (Technovation guide target: 150–250) — {'PASS' if checks['abstract_150_250'] else 'FAIL'}.")
md.append(f"- Keywords: **{len(keywords)}** (maximum 6) — {'PASS' if checks['keywords_max_6'] else 'FAIL'}.")
md.append(f"- Main text, Introduction through Conclusion: **{len(words(main_text))} words** (Technovation article guide: 5,000–10,000) — {'PASS' if checks['main_text_5000_10000'] else 'FAIL'}.")
md.append(f"- Words before References including title/abstract/admin sections: **{len(words(pre_refs))}**.")
md.append("")
md.append("## Scientific-integrity QA")
md.append("")
md.append(f"- References: **{len(reference_entries)}**; DOI-bearing references: **{len(doi_matches)}** — {'PASS' if checks['reference_entries_17'] and checks['doi_entries_17'] else 'FAIL'}.")
md.append(f"- Firm composition table present: **{FIRM.exists()}**; industry composition table present: **{INDUSTRY.exists()}**.")
md.append(f"- Locked prohibited-claim hits: **{len(prohibited_hits)}** — {'PASS' if not prohibited_hits else 'FAIL'}.")
md.append(f"- Required transparency language missing: **{len(missing_required)}** — {'PASS' if not missing_required else 'FAIL'}.")
md.append("")
md.append("## Hostile-review verdict")
md.append("")
if scientific_gate and journal_gate:
    md.append("**SCIENTIFIC CONTENT: READY FOR TECHNOVATION SUBMISSION ASSEMBLY.** The paper now states the sample-relative frontier, the 21-firm limit, industry concentration, H5 inference sensitivity, non-causal estimand, and H3 support failure directly. None of these residual scientific limitations can be honestly eliminated by additional specification search without changing the study itself.")
else:
    md.append("**REVISION REQUIRED BEFORE SUBMISSION ASSEMBLY.** See failed checks above.")
md.append("")
md.append("The strongest remaining reviewer vulnerabilities are substantive rather than hidden reporting defects:")
for risk in report["irreducible_scientific_risks"]:
    md.append(f"- {risk}")
md.append("")
md.append("These limitations should remain visible. In particular, the manuscript must not convert the predominantly negative H2 sensitivity pattern into a new post-hoc disadvantage hypothesis, and H5 must remain qualified directional evidence rather than a confirmed network effect.")
md.append("")
md.append("## Administrative submission blockers")
md.append("")
if admin_placeholders:
    for p in admin_placeholders:
        md.append(f"- `{p}`")
else:
    md.append("- None detected.")
md.append("")
md.append("Administrative placeholders do not affect the scientific lock, but the manuscript is not portal-submittable until author identity/affiliation, corresponding-author details, funding, conflicts, and CRediT contributions are completed as applicable.")
md.append("")
md.append("## Final recommendation")
md.append("")
if scientific_gate and journal_gate:
    md.append("**PROCEED TO SUBMISSION ASSEMBLY — TECHNOVATION.** Do not run additional outcome-seeking models. Complete administrative metadata, build the journal-formatted submission file/figures, perform a final visual/reference cross-check, and prepare the cover letter.")
else:
    md.append("**HOLD — FIX FAILED QA ITEMS BEFORE SUBMISSION ASSEMBLY.**")

(ROOT / "FINAL_TECHNOVATION_AUDIT_V2.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
