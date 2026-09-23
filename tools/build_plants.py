#!/usr/bin/env python3
"""สร้าง plants.html จาก data/plant-register.csv

วิธีใช้ (รันที่โฟลเดอร์หลักของ repo):
    python3 tools/build_plants.py

แก้ข้อมูลพรรณไม้ที่ data/plant-register.csv แล้วรันสคริปต์นี้ใหม่ทุกครั้ง
อย่าแก้ plants.html ด้วยมือ เพราะจะถูกเขียนทับ
"""
import csv
import html
import json
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "plant-register.csv"
OUT = ROOT / "plants.html"
PHOTOS = ROOT / "data" / "plant-photos.csv"
DATA_JS = ROOT / "js" / "plants-data.js"

CODE_RE = re.compile(r"^(7-31170-001-\d{3})(?:/(\d+))?$")
ZONE_RE = re.compile(r"(?:พื้นที่ศึกษาที่|โซน)\s*(\d+)")
RANKS = {"var.", "subsp.", "ssp.", "f."}


def esc(s):
    return html.escape(s, quote=True)


def sci_html(name):
    """ชื่อสกุล คำระบุชนิด และชื่อหลัง var./subsp./f. เป็นตัวเอียง ชื่อผู้ตั้งชื่อไม่เอียง"""
    toks = name.split()
    out = []
    italic_next = False
    for i, t in enumerate(toks):
        is_epithet = i == 1 and re.fullmatch(r"[a-z][a-z-]+", t) is not None
        if i == 0 or is_epithet or (italic_next and re.fullmatch(r"[a-z][a-z-]+", t)):
            out.append(f"<i>{esc(t)}</i>")
        else:
            out.append(esc(t))
        italic_next = t in RANKS
    return " ".join(out)


def or_pending(s, fmt=esc):
    return fmt(s) if s else '<span class="pending">อยู่ระหว่างรวบรวมข้อมูล</span>'


def zone_of(loc):
    m = ZONE_RE.search(loc)
    return int(m.group(1)) if m else None


def load():
    species = OrderedDict()
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = row["รหัสพรรณไม้"].strip()
            m = CODE_RE.match(code)
            if not m:
                raise SystemExit(f"รหัสพรรณไม้ไม่ถูกรูปแบบ: {code!r}")
            sp = species.setdefault(m.group(1), {
                "code": m.group(1),
                "thai": row["ชื่อพรรณไม้"],
                "sci": row["ชื่อวิทยาศาสตร์"],
                "family": row["ชื่อวงศ์"],
                "habit": row["ลักษณะวิสัย"],
                "feature": row["ลักษณะเด่นของพืช"],
                "locs": OrderedDict(),
            })
            loc = row["บริเวณที่พบ"]
            sp["locs"].setdefault(loc, []).append(code)
    return sorted(species.values(), key=lambda s: s["code"])


def card(sp):
    n = sum(len(v) for v in sp["locs"].values())
    zones = sorted({z for z in (zone_of(l) for l in sp["locs"]) if z is not None})
    search = " ".join([sp["code"], sp["thai"], sp["sci"], sp["family"]]).lower()
    locs = "".join(
        f"<li>{esc(loc)} <span class=\"n\">({len(codes)} ต้น)</span>"
        f"<br><span class=\"codes\">{esc(', '.join(codes))}</span></li>"
        for loc, codes in sp["locs"].items()
    )
    return f"""    <article class="plant" id="p{sp['code'][-3:]}" data-habit="{esc(sp['habit'])}" data-zones=" {' '.join(map(str, zones))} " data-search="{esc(search)}">
      <p class="code">{esc(sp['code'])}</p>
      <h3>{esc(sp['thai'])}</h3>
      <p class="sci">{or_pending(sp['sci'], sci_html)}</p>
      <dl>
        <dt>วงศ์</dt><dd>{or_pending(sp['family'])}</dd>
        <dt>ลักษณะวิสัย</dt><dd>{or_pending(sp['habit'])}</dd>
        <dt>ลักษณะเด่น</dt><dd>{or_pending(sp['feature'])}</dd>
      </dl>
      <details>
        <summary>บริเวณที่พบ · {n} ต้น</summary>
        <ul>{locs}</ul>
      </details>
    </article>
"""


def main():
    species = load()
    trees = sum(sum(len(v) for v in s["locs"].values()) for s in species)
    habits = sorted({s["habit"] for s in species if s["habit"]})
    zones = sorted({z for s in species for l in s["locs"] for z in [zone_of(l)] if z is not None})
    habit_opts = "".join(f'<option value="{esc(h)}">{esc(h)}</option>' for h in habits)
    zone_opts = "".join(f'<option value="{z}">พื้นที่ศึกษาที่ {z}</option>' for z in zones)
    cards = "".join(card(s) for s in species)
    page = TEMPLATE.format(
        n_species=len(species), n_trees=f"{trees:,}",
        habit_opts=habit_opts, zone_opts=zone_opts, cards=cards,
    )
    OUT.write_text(page, encoding="utf-8")
    print(f"เขียน {OUT.name}: {len(species)} ชนิด {trees} ต้น")
    write_data_js(species)


def load_photos():
    if not PHOTOS.exists():
        return {}
    with PHOTOS.open(encoding="utf-8-sig", newline="") as f:
        return {r["รหัสชนิด"]: r for r in csv.DictReader(f) if (ROOT / r["ไฟล์"]).exists()}


def write_data_js(species):
    """ข้อมูลพรรณไม้สำหรับหน้าแรก (พรรณไม้ประจำวัน)"""
    photos = load_photos()
    out = []
    for sp in species:
        names = re.split(r"[\s,]+", sp["thai"], maxsplit=1)
        ph = photos.get(sp["code"])
        out.append({
            "c": sp["code"][-3:],
            "n": names[0],
            "a": names[1] if len(names) > 1 else "",
            "s": sci_html(sp["sci"]) if sp["sci"] else "",
            "h": sp["habit"],
            "f": sp["feature"],
            "l": [[loc, len(codes)] for loc, codes in sp["locs"].items()],
            "p": ph and {"src": ph["ไฟล์"], "by": ph["ผู้ถ่าย"], "lic": ph["สัญญาอนุญาต"],
                         "licUrl": ph["ลิงก์สัญญาอนุญาต"], "url": ph["ที่มา"]},
        })
    DATA_JS.parent.mkdir(exist_ok=True)
    DATA_JS.write_text(
        "// สร้างจาก data/plant-register.csv และ data/plant-photos.csv ด้วย tools/build_plants.py ห้ามแก้ด้วยมือ\n"
        f"window.PLANTS = {json.dumps(out, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8")
    print(f"เขียน {DATA_JS.relative_to(ROOT)}: {len(out)} ชนิด มีภาพ {sum(1 for o in out if o['p'])} ชนิด")


TEMPLATE = """<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ทำเนียบพรรณไม้ | สวนพฤกษศาสตร์โรงเรียน โรงเรียนละหานทรายรัชดาภิเษก</title>
<meta name="description" content="ทำเนียบพรรณไม้ในสวนพฤกษศาสตร์โรงเรียน โรงเรียนละหานทรายรัชดาภิเษก">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap" rel="stylesheet">
<!-- ไฟล์นี้สร้างจาก data/plant-register.csv ด้วย tools/build_plants.py ห้ามแก้ด้วยมือ -->
<style>
  :root {{ --green:#2f6b3a; --leaf:#6a9a4f; --bg:#f6f8f3; --ink:#1f2a22; --muted:#5b6660; --line:#dfe7da; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:'Sarabun',sans-serif; background:var(--bg); color:var(--ink); line-height:1.6; }}
  header {{ background:var(--green); color:#fff; padding:40px 16px 32px; text-align:center; }}
  header .leaf {{ font-size:44px; line-height:1; }}
  h1 {{ margin:10px 0 4px; font-size:clamp(24px,5vw,36px); }}
  header p {{ margin:0; opacity:.9; }}
  nav {{ max-width:1080px; margin:0 auto; padding:16px 16px 0; font-size:15px; }}
  nav a {{ color:var(--green); }}
  main {{ max-width:1080px; margin:0 auto; padding:16px 16px 40px; }}
  .notice {{ background:#fff; border-left:5px solid var(--leaf); padding:16px 18px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
  .notice strong {{ color:var(--green); }}
  .tools {{ display:flex; flex-wrap:wrap; gap:8px; margin:20px 0 8px; }}
  .tools input, .tools select {{ font:inherit; padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); min-width:0; }}
  .tools input {{ flex:1 1 240px; }}
  .tools select {{ flex:1 1 160px; }}
  .count {{ color:var(--muted); font-size:15px; margin:0 0 12px; }}
  .plants {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }}
  .plant {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; min-width:0; }}
  .plant .code {{ margin:0; font-size:13px; color:var(--muted); }}
  .plant h3 {{ margin:0; color:var(--green); font-size:18px; }}
  .plant .sci {{ margin:0 0 8px; }}
  .plant dl {{ margin:0; font-size:15px; display:grid; grid-template-columns:auto 1fr; gap:2px 10px; }}
  .plant dt {{ font-weight:600; color:var(--muted); }}
  .plant dd {{ margin:0; }}
  details {{ margin-top:10px; font-size:15px; }}
  summary {{ cursor:pointer; color:var(--green); font-weight:600; }}
  details ul {{ margin:6px 0 0; padding-left:20px; }}
  details li {{ margin-bottom:4px; }}
  .n {{ color:var(--muted); }}
  .codes {{ font-size:13px; color:var(--muted); overflow-wrap:anywhere; }}
  .empty {{ color:var(--muted); }}
  .pending {{ color:var(--muted); font-style:normal; }}
  footer {{ text-align:center; font-size:14px; color:var(--muted); padding:20px 16px 32px; }}
</style>
</head>
<body>
<header>
  <div class="leaf" aria-hidden="true">🌿</div>
  <h1>ทำเนียบพรรณไม้</h1>
  <p>สวนพฤกษศาสตร์โรงเรียน โรงเรียนละหานทรายรัชดาภิเษก</p>
</header>
<nav><a href="./">← กลับหน้าแรก</a></nav>
<main>
  <div class="notice">
    <strong>{n_species} ชนิด · {n_trees} ต้น</strong><br>
    ข้อมูลจากทะเบียนพรรณไม้ของโรงเรียน รหัสสมาชิก 7-31170-001
  </div>

  <div class="tools" role="search">
    <input id="q" type="search" placeholder="ค้นหาชื่อไทย ชื่อวิทยาศาสตร์ วงศ์ หรือรหัส" aria-label="ค้นหาพรรณไม้">
    <select id="habit" aria-label="ลักษณะวิสัย"><option value="">ลักษณะวิสัยทั้งหมด</option>{habit_opts}</select>
    <select id="zone" aria-label="พื้นที่ศึกษา"><option value="">ทุกพื้นที่ศึกษา</option>{zone_opts}</select>
  </div>
  <p class="count" id="count" aria-live="polite">แสดง {n_species} ชนิด</p>

  <div class="plants" id="plants">
{cards}  </div>
  <p class="empty" id="empty" hidden>ไม่พบพรรณไม้ที่ตรงกับการค้นหา</p>
</main>
<footer>© งานสวนพฤกษศาสตร์โรงเรียน โรงเรียนละหานทรายรัชดาภิเษก</footer>
<script>
(function () {{
  var q = document.getElementById('q'), habit = document.getElementById('habit'), zone = document.getElementById('zone');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.plant'));
  var count = document.getElementById('count'), empty = document.getElementById('empty');
  function apply() {{
    var t = q.value.trim().toLowerCase(), h = habit.value, z = zone.value, shown = 0;
    cards.forEach(function (c) {{
      var ok = (!t || c.dataset.search.indexOf(t) !== -1) &&
               (!h || c.dataset.habit === h) &&
               (!z || c.dataset.zones.indexOf(' ' + z + ' ') !== -1);
      c.hidden = !ok;
      if (ok) shown++;
    }});
    count.textContent = 'แสดง ' + shown + ' ชนิด';
    empty.hidden = shown !== 0;
  }}
  q.addEventListener('input', apply);
  habit.addEventListener('change', apply);
  zone.addEventListener('change', apply);
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
