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
# กลุ่มลักษณะวิสัย 6 กลุ่ม (ใช้ในตัวกรองหน้าทำเนียบ และหน้าสมุดภาพในหน้าแรก)
GROUPS = [
    ("tree", "ไม้ต้น"),
    ("herb", "ไม้ล้มลุก"),
    ("shrub", "ไม้พุ่ม"),
    ("climber", "ไม้เลื้อย"),
    ("grass", "หญ้า เฟิร์น และไม้น้ำ"),
    ("palm", "ปาล์มและไผ่"),
]


def group_of(habit):
    if "ปาล์ม" in habit or "ไผ่" in habit:
        return "palm"
    if habit.startswith("ไม้ต้น"):
        return "tree"
    if any(w in habit for w in ("หญ้า", "เฟิร์น", "ไม้น้ำ")):
        return "grass"
    if habit.startswith("ไม้ล้มลุก"):
        return "herb"
    if habit.startswith("ไม้พุ่ม"):
        return "shrub"
    if "เลื้อย" in habit:
        return "climber"
    return "herb"


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


def split_names(thai):
    names = re.split(r"[\s,]+", thai, maxsplit=1)
    return names[0], (names[1] if len(names) > 1 else "")


def card(sp, photo):
    n = sum(len(v) for v in sp["locs"].values())
    zones = sorted({z for z in (zone_of(l) for l in sp["locs"]) if z is not None})
    search = " ".join([sp["code"], sp["thai"], sp["sci"], sp["family"]]).lower()
    name, aka = split_names(sp["thai"])
    locs = "".join(
        f"<li>{esc(loc)} <span class=\"n\">{len(codes)} ต้น</span>"
        f"<span class=\"codes\">{esc(', '.join(codes))}</span></li>"
        for loc, codes in sp["locs"].items()
    )
    if photo:
        pic = (f'<img src="{esc(photo["ไฟล์"])}" alt="ภาพตัวอย่าง{esc(name)}" loading="lazy" '
               f'decoding="async" width="720" height="540">')
        credit = (f'<p class="credit">ภาพตัวอย่างชนิดพันธุ์ โดย {esc(photo["ผู้ถ่าย"])} '
                  f'(<a href="{esc(photo["ที่มา"])}" target="_blank" rel="noopener">iNaturalist</a>) '
                  f'<a href="{esc(photo["ลิงก์สัญญาอนุญาต"])}" target="_blank" rel="noopener">{esc(photo["สัญญาอนุญาต"])}</a></p>')
    else:
        pic, credit = "", ""
    aka_html = f'<p class="aka">ชื่ออื่น {esc(aka)}</p>' if aka else ""
    feat = f'<p class="feat"><b>สังเกตดู</b> {esc(sp["feature"])}</p>' if sp["feature"] else ""
    return f"""    <article class="plant" id="p{sp['code'][-3:]}" data-group="{group_of(sp['habit'])}" data-zones=" {' '.join(map(str, zones))} " data-search="{esc(search)}">
      <figure class="ph">{pic}</figure>
      <div class="body">
        <h2>{esc(name)}</h2>
        <p class="sci">{or_pending(sp['sci'], sci_html)}</p>
        {aka_html}
        <p class="tags"><span class="tag">{or_pending(sp['habit'])}</span> <span class="fam">วงศ์ {or_pending(sp['family'])}</span></p>
        {feat}
        <details>
          <summary>พบ {n} ต้นในโรงเรียน</summary>
          <p class="code">รหัสพรรณไม้ {esc(sp['code'])}</p>
          <ul>{locs}</ul>
        </details>
        {credit}
      </div>
    </article>
"""


def main():
    species = load()
    photos = load_photos()
    trees = sum(sum(len(v) for v in s["locs"].values()) for s in species)
    counts = {k: sum(1 for s in species if group_of(s["habit"]) == k) for k, _ in GROUPS}
    zones = sorted({z for s in species for l in s["locs"] for z in [zone_of(l)] if z is not None})
    habit_opts = "".join(f'<option value="{k}">{esc(label)} ({counts[k]})</option>' for k, label in GROUPS)
    zone_opts = "".join(f'<option value="{z}">พื้นที่ศึกษาที่ {z}</option>' for z in zones)
    cards = "".join(card(s, photos.get(s["code"])) for s in species)
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
        name, aka = split_names(sp["thai"])
        ph = photos.get(sp["code"])
        out.append({
            "c": sp["code"][-3:],
            "n": name,
            "a": aka,
            "s": sci_html(sp["sci"]) if sp["sci"] else "",
            "h": sp["habit"],
            "g": group_of(sp["habit"]),
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
<meta name="description" content="พรรณไม้ {n_species} ชนิดในสวนพฤกษศาสตร์โรงเรียน โรงเรียนละหานทรายรัชดาภิเษก">
<meta name="theme-color" content="#E8EFD8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anuphan:wght@400;500;600&family=Chonburi&display=swap" rel="stylesheet">
<link rel="stylesheet" href="css/site.css">
<link rel="icon" type="image/png" href="img/favicon.png">
<!-- ไฟล์นี้สร้างจาก data/plant-register.csv ด้วย tools/build_plants.py ห้ามแก้ด้วยมือ -->
<style>
  .wrap.wide {{ max-width:1120px; }}
  .tools {{ display:flex; flex-wrap:wrap; gap:10px; margin:24px 0 10px; }}
  .tools input, .tools select {{
    font:500 16px/1.3 var(--body); color:var(--ink); background:var(--card);
    border:2px solid var(--ink); border-radius:14px; padding:12px 14px; min-width:0;
  }}
  .tools input {{ flex:1 1 100%; }}
  .tools select {{ flex:1 1 160px; }}
  @media (min-width:720px) {{ .tools input {{ flex:2 1 320px; }} }}
  .count {{ margin:0 0 14px; font-size:15px; color:var(--ink-soft); }}
  .plants {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(290px, 1fr)); gap:18px; }}
  .plant {{
    background:var(--card); border:2px solid var(--ink); border-radius:6px 34px 6px 34px;
    overflow:hidden; min-width:0; scroll-margin-top:16px; display:flex; flex-direction:column;
  }}
  .plant[hidden] {{ display:none; }}
  .plant:target {{ outline:4px solid var(--turmeric); outline-offset:3px; }}
  .ph {{ margin:0; aspect-ratio:4/3; background:var(--leaf); border-bottom:2px solid var(--ink); position:relative; overflow:hidden; }}
  .ph img {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block; }}
  .body {{ padding:14px 16px 16px; display:flex; flex-direction:column; flex:1; }}
  .plant h2 {{ font-family:var(--display); font-weight:400; font-size:28px; line-height:1.25; margin:0; overflow-wrap:anywhere; }}
  .sci {{ margin:2px 0 0; }}
  .aka {{ margin:2px 0 0; font-size:14px; color:var(--ink-soft); }}
  .tags {{ margin:10px 0 0; font-size:14px; display:flex; flex-wrap:wrap; gap:6px 10px; align-items:center; }}
  .tag {{ background:var(--turmeric); border:2px solid var(--ink); border-radius:999px; padding:1px 10px; font-weight:600; }}
  .fam {{ color:var(--ink-soft); }}
  .feat {{ margin:10px 0 0; font-size:15px; line-height:1.55; }}
  .feat b {{ font-weight:600; }}
  details {{ margin:12px 0 0; font-size:15px; }}
  summary {{ cursor:pointer; font-weight:600; }}
  details .code {{ margin:6px 0 0; font-size:13px; color:var(--ink-soft); }}
  details ul {{ margin:6px 0 0; padding-left:18px; }}
  details li {{ margin-bottom:6px; }}
  .n {{ font-weight:600; }}
  .codes {{ display:block; font-size:12.5px; color:var(--ink-soft); overflow-wrap:anywhere; }}
  .credit {{ margin:auto 0 0; padding-top:12px; font-size:12px; line-height:1.5; color:var(--ink-soft); }}
  .credit a {{ color:var(--ink-soft); }}
  .pending {{ color:var(--ink-soft); }}
  .empty {{ font-size:18px; padding:24px 0; }}
</style>
</head>
<body>
<div class="wrap wide">
  <a class="top" href="./">
    <img src="img/emblem.png" alt="" width="250" height="313">
    <div><b>สวนพฤกษศาสตร์โรงเรียน</b><span>โรงเรียนละหานทรายรัชดาภิเษก</span></div>
  </a>
  <main>
    <h1 class="page-title">ทำเนียบพรรณไม้</h1>
    <p class="lede">{n_species} ชนิด {n_trees} ต้นในโรงเรียน จากทะเบียนพรรณไม้ของโรงเรียน</p>

    <div class="tools" role="search">
      <input id="q" type="search" placeholder="พิมพ์ชื่อไทย ชื่อวิทยาศาสตร์ หรือรหัสบนป้าย" aria-label="ค้นหาพรรณไม้">
      <select id="habit" aria-label="กลุ่มลักษณะวิสัย"><option value="">ทุกลักษณะวิสัย</option>{habit_opts}</select>
      <select id="zone" aria-label="พื้นที่ศึกษา"><option value="">ทุกพื้นที่ศึกษา</option>{zone_opts}</select>
    </div>
    <p class="count" id="count" aria-live="polite">แสดง {n_species} ชนิด</p>

    <div class="plants" id="plants">
{cards}    </div>
    <p class="empty" id="empty" hidden>ไม่พบพรรณไม้ที่ตรงกับคำค้น ลองพิมพ์ชื่อสั้นลง หรือเลือก "ทุกพื้นที่ศึกษา"</p>
  </main>
  <footer>© งานสวนพฤกษศาสตร์โรงเรียน โรงเรียนละหานทรายรัชดาภิเษก</footer>
</div>
<script>
(function () {{
  var q = document.getElementById('q'), habit = document.getElementById('habit'), zone = document.getElementById('zone');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.plant'));
  var count = document.getElementById('count'), empty = document.getElementById('empty');
  function apply() {{
    var t = q.value.trim().toLowerCase(), h = habit.value, z = zone.value, shown = 0;
    cards.forEach(function (c) {{
      var ok = (!t || c.dataset.search.indexOf(t) !== -1) &&
               (!h || c.dataset.group === h) &&
               (!z || c.dataset.zones.indexOf(' ' + z + ' ') !== -1);
      c.hidden = !ok;
      if (ok) shown++;
    }});
    count.textContent = 'แสดง ' + shown + ' ชนิด';
    empty.hidden = shown !== 0;
  }}
  // เปิดจากปุ่ม "ดูทั้งหมด" ในหน้าแรก เช่น plants.html?group=tree
  var g = new URLSearchParams(location.search).get('group');
  if (g && habit.querySelector('option[value="' + g + '"]')) {{ habit.value = g; apply(); }}
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
