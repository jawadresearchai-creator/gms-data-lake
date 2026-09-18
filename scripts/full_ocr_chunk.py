#!/usr/bin/env python3
import argparse, json, os, re, statistics, unicodedata
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz
import pytesseract
from PIL import Image, ImageOps

def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\ufeff", "").replace("\x00", "")
    return re.sub(r"\s+", " ", s).strip()

def ocr_worker(pdf_path, start, end, lang, zoom, psm):
    doc = fitz.open(pdf_path)
    out = []
    for pno in range(start, end + 1):
        page = doc[pno - 1]
        embedded = norm(page.get_text("text", sort=True))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, colorspace=fitz.csGRAY)
        im = Image.frombytes("L", [pix.width, pix.height], pix.samples)
        im = ImageOps.autocontrast(im)
        data = pytesseract.image_to_data(im, lang=lang, config=f"--oem 1 --psm {psm}", output_type=pytesseract.Output.DICT)
        tokens, confs = [], []
        for txt, conf in zip(data.get("text", []), data.get("conf", [])):
            txt = norm(txt)
            try:
                cf = float(conf)
            except Exception:
                cf = -1
            if txt:
                tokens.append(txt)
                if cf >= 0:
                    confs.append(cf)
        ocr = norm(" ".join(tokens))
        mean_conf = round(statistics.mean(confs), 2) if confs else None
        out.append({
            "page": pno,
            "ocr_text": ocr,
            "ocr_chars": len(ocr),
            "mean_conf": mean_conf,
            "embedded_text": embedded,
            "embedded_chars": len(embedded),
            "lang": lang,
            "zoom": zoom,
            "psm": psm,
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--lang", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--zoom", type=float, default=2.6)
    ap.add_argument("--psm", type=int, default=3)
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.pdf)
    maxp = len(doc)
    doc.close()
    start = max(1, args.start)
    end = min(args.end, maxp)
    if start > end:
        raise SystemExit("invalid page range")

    total = end - start + 1
    workers = max(1, min(args.workers, total))
    step = (total + workers - 1) // workers
    ranges = []
    s = start
    while s <= end:
        e = min(end, s + step - 1)
        ranges.append((s,e))
        s = e + 1

    recs = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(ocr_worker, args.pdf, s, e, args.lang, args.zoom, args.psm) for s,e in ranges]
        for fut in as_completed(futs):
            recs.extend(fut.result())
    recs.sort(key=lambda x:x["page"])

    stem = f"{args.key}_{start:05d}_{end:05d}"
    jsonl = outdir / f"{stem}.jsonl"
    txt = outdir / f"{stem}.txt"
    qa = outdir / f"{stem}_qa.json"

    with jsonl.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with txt.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(f"\n===== PAGE {r['page']} | OCR CONF {r['mean_conf']} =====\n{r['ocr_text']}\n")

    confs = [r["mean_conf"] for r in recs if r["mean_conf"] is not None]
    low = [r["page"] for r in recs if r["mean_conf"] is None or r["mean_conf"] < 45 or r["ocr_chars"] < 40]
    summary = {
        "book_key": args.key,
        "start_page": start,
        "end_page": end,
        "pages": len(recs),
        "lang": args.lang,
        "zoom": args.zoom,
        "psm": args.psm,
        "mean_page_conf": round(statistics.mean(confs),2) if confs else None,
        "median_page_conf": round(statistics.median(confs),2) if confs else None,
        "low_conf_or_low_text_pages": low,
        "low_conf_or_low_text_count": len(low),
        "total_ocr_chars": sum(r["ocr_chars"] for r in recs),
        "total_embedded_chars": sum(r["embedded_chars"] for r in recs),
    }
    qa.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == "__main__":
    main()
