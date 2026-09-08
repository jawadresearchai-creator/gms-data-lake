import json
from pathlib import Path

p = Path("output_final_lock/final_analysis_lock.json")
obj = json.loads(p.read_text(encoding="utf-8"))
# Value is frozen from the estimator-hardening checkpoint for the p2_100_w2 primary panel.
obj.setdefault("selection_adjustment", {})["primary_overlap_ess"] = 134.04193348016761
p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
print("Corrected primary_overlap_ess metadata to 134.04193348016761")
