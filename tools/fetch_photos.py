#!/usr/bin/env python3
"""หาภาพตัวอย่างพรรณไม้ (สัญญาอนุญาตเปิด) ตามชื่อวิทยาศาสตร์ใน data/plant-register.csv

วิธีใช้ (รันที่โฟลเดอร์หลักของ repo):
    pip install pillow
    python3 tools/fetch_photos.py
    python3 tools/build_plants.py

- หาจาก iNaturalist เฉพาะภาพที่ใช้สัญญาอนุญาต CC0, CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA
- ย่อภาพเป็นกว้าง 720 px เก็บที่ img/plants/<รหัสชนิด>.jpg
- บันทึกเครดิตและสัญญาอนุญาตของทุกภาพที่ data/plant-photos.csv (ต้องแสดงเครดิตบนเว็บทุกภาพ)
- ชนิดที่มีภาพแล้วจะข้าม ถ้าอยากเปลี่ยนภาพ ให้ลบแถวนั้นใน CSV และลบไฟล์ภาพ แล้วรันใหม่
- ภาพเป็นภาพของชนิดเดียวกัน ไม่ใช่ต้นในโรงเรียน
"""
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "data" / "plant-register.csv"
OUT_CSV = ROOT / "data" / "plant-photos.csv"
IMG_DIR = ROOT / "img" / "plants"
FIELDS = ["รหัสชนิด", "ชื่อวิทยาศาสตร์ที่ค้น", "ชื่อที่พบ", "ไฟล์", "ผู้ถ่าย",
          "สัญญาอนุญาต", "ลิงก์สัญญาอนุญาต", "ที่มา"]
UA = "LRPBotanicSchoolSite/1.0 (https://lrp-botanic.github.io; school botanical garden)"
OPEN = {
    "cc0": ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "cc-by": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "cc-by-sa": ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "cc-by-nc": ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/"),
    "cc-by-nc-sa": ("CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0/"),
}
WIDTH = 720


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def query_names(sci):
    """ชื่อที่จะค้น: ชื่อเต็มระดับต่ำกว่าชนิด (ถ้ามี) แล้วตามด้วยชื่อทวินาม"""
    toks = sci.split()
    if len(toks) < 2 or not re.fullmatch(r"[a-z][a-z-]+", toks[1]):
        return []  # เช่น "Nephrolepis sp." ไม่รู้ชนิด
    names = []
    for i, t in enumerate(toks):
        if t in ("var.", "subsp.", "ssp.") and i + 1 < len(toks):
            names.append(f"{toks[0]} {toks[1]} {t.rstrip('.').replace('subsp', 'ssp')} {toks[i + 1]}")
    names.append(f"{toks[0]} {toks[1]}")
    return names


def inat_photo(name):
    q = urllib.parse.urlencode({"q": name, "is_active": "true", "per_page": 10})
    res = json.loads(get(f"https://api.inaturalist.org/v1/taxa?{q}"))["results"]
    target = name.lower().replace(" ssp ", " ").replace(" var ", " ")
    for t in res:
        names = {t.get("name", "").lower(), (t.get("matched_term") or "").lower()}
        if target not in names:
            continue
        time.sleep(1)
        full = json.loads(get(f"https://api.inaturalist.org/v1/taxa/{t['id']}"))["results"][0]
        for tp in full.get("taxon_photos", []):
            p = tp["photo"]
            lic = (p.get("license_code") or "").lower()
            if lic in OPEN and p.get("medium_url"):
                author = re.sub(r"^\(c\)\s*", "", p.get("attribution", "")).split(",")[0].strip()
                return {
                    "found": t["name"],
                    "url": p["medium_url"].replace("/medium.", "/large."),
                    "author": author or "ไม่ระบุชื่อ",
                    "license": OPEN[lic][0],
                    "license_url": OPEN[lic][1],
                    "source": f"https://www.inaturalist.org/photos/{p['id']}",
                }
    return None


def main():
    species = {}
    with REGISTER.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            species.setdefault(row["รหัสพรรณไม้"][:15], row["ชื่อวิทยาศาสตร์"])
    done = {}
    if OUT_CSV.exists():
        with OUT_CSV.open(encoding="utf-8-sig", newline="") as f:
            done = {r["รหัสชนิด"]: r for r in csv.DictReader(f)}
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for code, sci in sorted(species.items()):
        if code in done and (ROOT / done[code]["ไฟล์"]).exists():
            continue
        photo = None
        for name in query_names(sci):
            try:
                photo = inat_photo(name)
            except Exception as e:  # เครือข่ายขัดข้อง ข้ามไปก่อน รันใหม่ได้
                print(f"{code} {name}: {e}", file=sys.stderr)
            time.sleep(1)
            if photo:
                photo["query"] = name
                break
        if not photo:
            missing.append(f"{code} {sci}")
            continue
        im = Image.open(io.BytesIO(get(photo["url"]))).convert("RGB")
        if im.width > WIDTH:
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        rel = f"img/plants/{code[-3:]}.jpg"
        im.save(ROOT / rel, "JPEG", quality=72, optimize=True, progressive=True)
        done[code] = {
            "รหัสชนิด": code, "ชื่อวิทยาศาสตร์ที่ค้น": photo["query"], "ชื่อที่พบ": photo["found"],
            "ไฟล์": rel, "ผู้ถ่าย": photo["author"], "สัญญาอนุญาต": photo["license"],
            "ลิงก์สัญญาอนุญาต": photo["license_url"], "ที่มา": photo["source"],
        }
        print(f"{code} {sci} -> {photo['found']} ({photo['license']})")
        time.sleep(1)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for code in sorted(done):
            w.writerow(done[code])
    print(f"มีภาพ {len(done)} จาก {len(species)} ชนิด")
    if missing:
        print("ไม่พบภาพ:", *missing, sep="\n  ")


if __name__ == "__main__":
    main()
