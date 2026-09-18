#!/usr/bin/env python3
import argparse, json, statistics
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--chunks",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    src=Path(args.chunks); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    keys=["bukhari_ar_ur","muslim_ar_ur","bukhari_en","muslim_en"]
    audit={"books":{}}
    for key in keys:
        files=sorted(src.glob(f"{key}_*.jsonl"))
        recs=[]
        for fp in files:
            with fp.open(encoding="utf-8") as f:
                for line in f:
                    recs.append(json.loads(line))
        recs.sort(key=lambda r:r["page"])
        uniq={r["page"]:r for r in recs}
        recs=[uniq[p] for p in sorted(uniq)]
        with (out/f"{key}_full_ocr.jsonl").open("w",encoding="utf-8") as f:
            for r in recs: f.write(json.dumps(r,ensure_ascii=False)+"\n")
        with (out/f"{key}_full_ocr.txt").open("w",encoding="utf-8") as f:
            for r in recs:
                f.write(f"\n===== PAGE {r['page']} | OCR CONF {r['mean_conf']} =====\n{r['ocr_text']}\n")
        conf=[r["mean_conf"] for r in recs if r.get("mean_conf") is not None]
        low=[r["page"] for r in recs if r.get("mean_conf") is None or r.get("mean_conf",0)<45 or r.get("ocr_chars",0)<40]
        audit["books"][key]={
            "pages":len(recs),
            "first_page":recs[0]["page"] if recs else None,
            "last_page":recs[-1]["page"] if recs else None,
            "mean_page_conf":round(statistics.mean(conf),2) if conf else None,
            "median_page_conf":round(statistics.median(conf),2) if conf else None,
            "low_conf_or_low_text_count":len(low),
            "low_conf_or_low_text_pages":low,
            "total_ocr_chars":sum(r.get("ocr_chars",0) for r in recs),
            "total_embedded_chars":sum(r.get("embedded_chars",0) for r in recs),
        }
    (out/"FULL_OCR_AUDIT.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"FULL_OCR_README.md").open("w",encoding="utf-8") as f:
        f.write("# Full page-image OCR corpus\n\n")
        f.write("All four source books were rendered page-by-page and passed through Tesseract OCR. Arabic/Urdu books used urd+ara+eng; English editions used eng. The original embedded text is retained in each JSONL record only for audit comparison; ocr_text is the true page-image OCR result.\n\n")
        for k,v in audit["books"].items():
            f.write(f"- **{k}**: {v['pages']} pages; mean OCR confidence {v['mean_page_conf']}; low-confidence/low-text pages {v['low_conf_or_low_text_count']}.\n")
        f.write("\nNo OCR output is automatically treated as publication-final. The 30 selected hadith records require source-page visual verification, exact narrator/matn/translation boundary checks, and numbering reconciliation.\n")
    print(json.dumps(audit,ensure_ascii=False))
if __name__=="__main__": main()
