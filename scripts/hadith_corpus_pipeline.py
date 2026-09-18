#!/usr/bin/env python3
import argparse, csv, hashlib, json, os, re, shutil, subprocess, tempfile, time, unicodedata, zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz

BOOKS = [
    {
        "key":"bukhari_ar_ur",
        "filename":"01 - Sahih al-Bukhari (Arabic & Urdu Complete) - Imam Bukhari.pdf",
        "collection":"Sahih al-Bukhari","language":"Arabic+Urdu","ocr_lang":"ara+urd+eng"
    },
    {
        "key":"muslim_ar_ur",
        "filename":"02 - Sahih Muslim (Arabic & Urdu Complete) - Imam Muslim.pdf",
        "collection":"Sahih Muslim","language":"Arabic+Urdu","ocr_lang":"ara+urd+eng"
    },
    {
        "key":"bukhari_en",
        "filename":"03 - Sahih al-Bukhari (English - M. Muhsin Khan).pdf",
        "collection":"Sahih al-Bukhari","language":"English","ocr_lang":"eng"
    },
    {
        "key":"muslim_en",
        "filename":"04 - Sahih Muslim (English - Abd-al-Hamid Siddiqui).pdf",
        "collection":"Sahih Muslim","language":"English","ocr_lang":"eng"
    },
]

TOPICS = [
(1,"Salah as a foundation of Islam",["islam is based on (the following) five","islam is based on five","بُنِيَ الْإِسْلاَمُ عَلَى خَمْس","بني الاسلام على خمس","اسلام (کا قصر پانچ ستونوں)","اسلام کی بنیاد پانچ"]),
(2,"Five daily prayers",["five prayers","five daily prayers","خمس صلوات","پانچ نماز"]),
(3,"Intention (Niyyah)",["actions depend upon intentions","actions are but by intention","الأعمال بالنيات","اعمال کا دارومدار نیت"]),
(4,"Wudu and purification",["ablution","wudu","وضوء","وضو"]),
(5,"Cleanliness of body, clothes and prayer place",["clean clothes","clean place","نجاسة","پاک کپڑ","پاک جگہ"]),
(6,"Prayer times",["times of the prayers","prayer time","مواقيت الصلاة","اوقات نماز"]),
(7,"Adhan",["call to prayers","adhan","adhaan","أذان","اذان"]),
(8,"Qiblah",["qibla","qiblah","قبلة","قبلہ"]),
(9,"Sutrah",["sutra","sutrah","سترة","سترہ"]),
(10,"Beginning prayer calmly / Takbir",["takbir","allahu akbar","تكبير","تکبیر"]),
(11,"Takbir in prayer",["takbir","تكبير","تکبیر"]),
(12,"Standing and recitation (Qiyam)",["standing in prayer","recitation in prayer","قيام","قیام","قراءت"]),
(13,"Al-Fatihah in prayer",["fatihah","fatiha","opening of the book","فاتحة","فاتحہ"]),
(14,"Ruku (bowing)",["bowing","ruku","ركوع","رکوع"]),
(15,"Rising from Ruku",["rising from bowing","sami allahu liman hamidah","سمع الله لمن حمده","رکوع سے"]),
(16,"Sujud (prostration)",["prostrating","prostration","sujud","سجود","سجد"]),
(17,"Sitting between two prostrations",["between the two prostrations","between two prostrations","بين السجدتين","دو سجدوں کے درمیان"]),
(18,"Rak'ah sequence and second Sujud",["rak'at","rakat","rak'ah","ركعة","رکعت"]),
(19,"Tashahhud",["tashahhud","at-tahiyyat","التشهد","تشہد"]),
(20,"Salam at the end of prayer",["taslim","salutation","salam at the end","التسليم","سلام پھیر"]),
(21,"Khushu and presence",["khushu","خشوع","humility in prayer"]),
(22,"Avoiding haste / calmness in movements",["hurried in prayer","hastily in prayer","طمأنينة","اطمینان","جلدی نماز"]),
(23,"Congregational prayer",["congregational prayer","prayer in congregation","الجماعة","باجماعت","جماعت"]),
(24,"Straightening the rows",["straighten the rows","rows in prayer","سووا صفوفكم","صفیں سیدھی","صفوں"]),
(25,"Fajr and Isha",["fajr","isha","morning prayer","night prayer","الفجر","العشاء","فجر","عشاء"]),
(26,"Friday prayer (Jumu'ah)",["friday prayer","jumu","الجمعة","جمعہ"]),
(27,"Witr and night prayer",["witr","tahajjud","night prayer","وتر","تهجد","تہجد"]),
(28,"Missed or forgotten prayer",["forgets a prayer","slept through prayer","missed prayer","نسي صلاة","نماز بھول","نماز رہ"]),
(29,"Travel and shortening prayer",["shortening the prayers","prayer during travel","traveller","قصر الصلاة","سفر","قصر"]),
(30,"Guarding and maintaining Salah",["guard the prayers","maintain the prayers","preserve the prayers","حافظوا على الصلوات","نمازوں کی حفاظت"]),
]

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
LATIN_RE = re.compile(r"[A-Za-z]")

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def clean_text(t):
    return t.replace("\x00","").replace("\ufeff","").strip()

def extract_chunk(args):
    pdf_path, start, end = args
    doc=fitz.open(pdf_path)
    out=[]
    for idx in range(start,end):
        t=clean_text(doc[idx].get_text("text", sort=True))
        out.append((idx+1,t))
    return out

def ocr_page(pdf_path, page_no, lang):
    try:
        import pytesseract
        doc=fitz.open(pdf_path)
        page=doc[page_no-1]
        pix=page.get_pixmap(matrix=fitz.Matrix(2.0,2.0), alpha=False)
        from PIL import Image
        im=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
        t=pytesseract.image_to_string(im,lang=lang,config="--psm 6")
        return clean_text(t)
    except Exception:
        return ""

def extract_book(book, source_dir, out_dir):
    pdf=source_dir/book["filename"]
    doc=fitz.open(pdf); n=len(doc); doc.close()
    workers=min(4, max(1, os.cpu_count() or 2))
    chunk=max(100, (n+workers*4-1)//(workers*4))
    ranges=[(str(pdf),s,min(s+chunk,n)) for s in range(0,n,chunk)]
    pages={}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs=[ex.submit(extract_chunk,r) for r in ranges]
        for f in as_completed(futs):
            for p,t in f.result(): pages[p]=t

    # OCR fallback only when embedded extraction is absent/very weak.
    ocr_candidates=[p for p,t in pages.items() if len(t.strip())<40]
    ocr_used=[]
    for p in ocr_candidates:
        ot=ocr_page(str(pdf),p,book["ocr_lang"])
        if len(ot)>len(pages[p])+20:
            pages[p]=ot; ocr_used.append(p)

    jsonl=out_dir/f'{book["key"]}_pages.jsonl'
    txt=out_dir/f'{book["key"]}_pages.txt'
    low=[]; blank=[]; repl=0; total=0; ar_total=0; lat_total=0
    with jsonl.open("w",encoding="utf-8") as fj, txt.open("w",encoding="utf-8") as ft:
        for p in range(1,n+1):
            t=pages.get(p,""); c=len(t); total+=c
            ar=len(ARABIC_RE.findall(t)); la=len(LATIN_RE.findall(t)); ar_total+=ar; lat_total+=la
            rr=t.count("\ufffd"); repl+=rr
            if c==0: blank.append(p)
            if c<80: low.append(p)
            rec={
                "book_key":book["key"],"collection":book["collection"],"language":book["language"],
                "page":p,"chars":c,"arabic_script_chars":ar,"latin_chars":la,
                "replacement_chars":rr,"method":"ocr_fallback" if p in ocr_used else "embedded_text",
                "text":t
            }
            fj.write(json.dumps(rec,ensure_ascii=False)+"\n")
            ft.write(f"\n===== PAGE {p} =====\n{t}\n")
    audit={
        "book_key":book["key"],"filename":book["filename"],"collection":book["collection"],"language":book["language"],
        "sha256":sha256(pdf),"pages":n,"total_chars":total,
        "blank_page_count":len(blank),"blank_pages":blank,
        "low_text_page_count":len(low),"low_text_pages_under_80_chars":low,
        "ocr_fallback_page_count":len(ocr_used),"ocr_fallback_pages":ocr_used,
        "replacement_char_count":repl,"arabic_script_chars_total":ar_total,"latin_chars_total":lat_total
    }
    return audit

def load_pages(path):
    recs=[]
    with open(path,encoding="utf-8") as f:
        for line in f: recs.append(json.loads(line))
    return recs

def parse_english_hadiths(recs,key):
    if key=="bukhari_en":
        marker=re.compile(r"Volume\s+(\d+),\s*Book\s+(\d+),\s*Number\s+(\d+):")
        def ref(m): return f'Volume {m.group(1)}, Book {m.group(2)}, Number {m.group(3)}'
    else:
        marker=re.compile(r"Book\s+(\d{3}),\s*Number\s+(\d{4}):")
        def ref(m): return f'Book {m.group(1)}, Number {m.group(2)}'
    out=[]; cur=None
    for pg in recs:
        text=pg["text"]; matches=list(marker.finditer(text))
        if not matches:
            if cur: cur["text"] += "\n"+text
            continue
        pos=0
        for j,m in enumerate(matches):
            if j==0 and cur:
                cur["text"] += "\n"+text[:m.start()]
                out.append(cur); cur=None
            if cur:
                out.append(cur)
            end=matches[j+1].start() if j+1<len(matches) else len(text)
            cur={"book_key":key,"collection":pg["collection"],"hadith_ref":ref(m),"start_page":pg["page"],"text":text[m.end():end].strip()}
        # cur continues to next page until next marker
    if cur: out.append(cur)
    return out

def norm(s):
    s=unicodedata.normalize("NFKC",s).lower()
    s=re.sub(r"\s+"," ",s)
    return s

def topic_hits(text):
    nt=norm(text); hits=[]
    for tid,title,terms in TOPICS:
        mt=[term for term in terms if norm(term) in nt]
        if mt: hits.append((tid,title,mt))
    return hits

def make_indexes(out_dir, audits):
    # hadith-level English anchor corpus
    all_h=[]
    for key in ["bukhari_en","muslim_en"]:
        recs=load_pages(out_dir/f"{key}_pages.jsonl")
        hs=parse_english_hadiths(recs,key)
        all_h.extend(hs)
    with open(out_dir/"english_hadith_records.jsonl","w",encoding="utf-8") as f:
        for h in all_h: f.write(json.dumps(h,ensure_ascii=False)+"\n")

    candidate_rows=[]
    for h in all_h:
        for tid,title,terms in topic_hits(h["text"]):
            candidate_rows.append([tid,title,h["collection"],h["hadith_ref"],h["start_page"],"; ".join(terms),re.sub(r"\s+"," ",h["text"])[:1200]])
    candidate_rows.sort(key=lambda r:(r[0],r[2],r[4]))
    with open(out_dir/"namaz_hadith_candidates_english.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["topic_id","topic","collection","hadith_ref","source_page","matched_terms","text_excerpt"]); w.writerows(candidate_rows)

    # all-language page hits, for retrieving exact Arabic/Urdu book wording
    page_rows=[]
    for b in BOOKS:
        recs=load_pages(out_dir/f'{b["key"]}_pages.jsonl')
        for pg in recs:
            for tid,title,terms in topic_hits(pg["text"]):
                page_rows.append([tid,title,b["key"],b["collection"],b["language"],pg["page"],pg["method"],"; ".join(terms),re.sub(r"\s+"," ",pg["text"])[:1200]])
    page_rows.sort(key=lambda r:(r[0],r[2],r[5]))
    with open(out_dir/"namaz_topic_page_index_all_languages.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["topic_id","topic","book_key","collection","language","page","extraction_method","matched_terms","page_excerpt"]); w.writerows(page_rows)

    topics_dir=out_dir/"topics"; topics_dir.mkdir(exist_ok=True)
    for tid,title,terms in TOPICS:
        slug=re.sub(r"[^a-z0-9]+","_",title.lower()).strip("_")
        rows=[r for r in candidate_rows if r[0]==tid]
        prows=[r for r in page_rows if r[0]==tid]
        with open(topics_dir/f"{tid:02d}_{slug}.md","w",encoding="utf-8") as f:
            f.write(f"# Day {tid:02d} — {title}\n\n")
            f.write("## English hadith candidates\n\n")
            if not rows: f.write("No automatic keyword candidate found; requires manual corpus search.\n")
            for r in rows:
                f.write(f"- **{r[2]} — {r[3]} — PDF p.{r[4]}**; matched: {r[5]}\n  - {r[6]}\n")
            f.write("\n## Arabic/Urdu/English page hits\n\n")
            for r in prows[:300]:
                f.write(f"- **{r[2]} p.{r[5]} ({r[6]})** — matched: {r[7]}\n")
            if len(prows)>300: f.write(f"\nAdditional page hits: {len(prows)-300}; see master CSV.\n")

    # audit checks and readme
    h_counts={}
    for h in all_h: h_counts[h["book_key"]]=h_counts.get(h["book_key"],0)+1
    summary={
        "books":audits,
        "parsed_english_hadith_records":h_counts,
        "namaz_candidate_rows":len(candidate_rows),
        "all_language_topic_page_hits":len(page_rows),
        "topics": [{"topic_id":a,"topic":b,"keywords":c} for a,b,c in TOPICS]
    }
    (out_dir/"AUDIT_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    with open(out_dir/"AUDIT_README.md","w",encoding="utf-8") as f:
        f.write("# Sahih Bukhari & Sahih Muslim — Audited Text Corpus for Namaz Series\n\n")
        f.write("## Extraction policy\n")
        f.write("- Embedded PDF text is the primary source because it preserves the publisher's Arabic/Urdu/English text more faithfully than re-OCR.\n")
        f.write("- Every page is extracted and tagged with its PDF page number.\n")
        f.write("- Pages with fewer than 40 extracted characters are sent through OCR fallback (Arabic+Urdu+English for bilingual editions; English for English editions).\n")
        f.write("- OCR-fallback pages remain explicitly tagged and must receive extra review before publication.\n")
        f.write("- No translation is generated by the pipeline. English and Urdu remain source-edition text.\n\n")
        f.write("## Corpus files\n")
        for b in BOOKS:
            f.write(f"- {b['key']}_pages.jsonl — page-level provenance and text\n- {b['key']}_pages.txt — readable page-marked extraction\n")
        f.write("- english_hadith_records.jsonl — parsed English hadith records with source pages.\n")
        f.write("- namaz_hadith_candidates_english.csv — hadith-level candidates grouped under the 30 Namaz topics.\n")
        f.write("- namaz_topic_page_index_all_languages.csv — source-page hits in Arabic/Urdu/English corpora for exact wording retrieval.\n")
        f.write("- topics/ — one review file per day/topic.\n\n")
        f.write("## Publication rule\n")
        f.write("Automatic topic matching is an index, not final religious verification. Before an image is generated, the chosen hadith must be checked against its Arabic/Urdu page and its published English translation page, with narrator and numbering reconciled.\n")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source",required=True); ap.add_argument("--output",required=True)
    a=ap.parse_args(); src=Path(a.source); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    audits=[]
    for b in BOOKS:
        print("EXTRACT",b["filename"],flush=True)
        audits.append(extract_book(b,src,out))
        print("DONE",b["key"],flush=True)
    make_indexes(out,audits)
    with zipfile.ZipFile(out/"AUDITED_CORPUS_PACKAGE.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in out.rglob("*"):
            if p.is_file() and p.name!="AUDITED_CORPUS_PACKAGE.zip":
                z.write(p,p.relative_to(out))
    print("COMPLETE",flush=True)

if __name__=="__main__": main()
