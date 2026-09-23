#!/usr/bin/env python3
"""นำเข้าทะเบียนพรรณไม้ (.xls) ของโรงเรียนเป็น data/plant-register.csv

วิธีใช้ (รันที่โฟลเดอร์หลักของ repo):
    pip install xlrd
    python3 tools/import_register.py โฟลเดอร์ที่มีไฟล์ทะเบียน
    python3 tools/build_plants.py

อ่านทุกไฟล์ .xls ในโฟลเดอร์ ยกเว้นไฟล์ที่ชื่อมีคำว่า "หัวแถวทุกหน้า" (ข้อมูลซ้ำ)
แล้วแก้ข้อมูลตามรายการ CODE_FIXES, DROP_CODES, DROP_SPECIES, TEXT_FIXES และ FIELD_FIXES ด้านล่าง
"""
import csv
import re
import sys
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "plant-register.csv"
HEADER = ["รหัสพรรณไม้", "ชื่อพรรณไม้", "ชื่อวิทยาศาสตร์", "ชื่อวงศ์",
          "ลักษณะวิสัย", "ลักษณะเด่นของพืช", "บริเวณที่พบ"]
CODE_RE = re.compile(r"^7-31170-001-(\d{3})(?:/(\d+))?$")

# รหัสพรรณไม้ที่พิมพ์ผิดในทะเบียน: รหัสเดิม -> รหัสที่ถูกต้อง
CODE_FIXES = {
    "7-31171-001-202/3": "7-31170-001-202/3",
}
# รหัสที่ซ้ำกันในทะเบียน ตัดออกทุกแถว (ครูสั่งตัด)
DROP_CODES = {
    "7-31170-001-040/140",
}
# ชนิดที่ตัดออกทั้งชนิด (ครูสั่งตัด เพราะหาภาพตัวอย่างไม่ได้)
DROP_SPECIES = {
    "008",  # ยางโอน
    "060",  # เฟิร์นใบทอง
    "176",  # นมงัว
}

# คำที่พิมพ์ผิดในชื่อวิทยาศาสตร์ (คอลัมน์ 2) และบริเวณที่พบ (คอลัมน์ 6)
TEXT_FIXES = [
    (2, "Ghretia", "Ehretia"),
    (2, "Hibiseus", "Hibiscus"),
    (2, "Fagraca", "Fagraea"),
    (2, "Echinodosus", "Echinodorus"),
    (2, "Penisetum", "Pennisetum"),
    (2, "Murdania", "Murdannia"),
    (2, "Chlorophylum", "Chlorophytum"),
    (2, "globusus", "globosus"),
    (2, "Epipremnum aureus", "Epipremnum aureum"),
    (2, "Garetn.", "Gaertn."),
    (6, "บริเวรอาคาร", "บริเวณอาคาร"),
    (6, "พื้นที่ศึกษาที่ 5 หน้าอาคาร 1", "พื้นที่ศึกษาที่ 5 พื้นที่หลังอาคาร 1"),
    (6, "พื้นที่ศึกษาที่ 10 หลังอาคาร 3", "พื้นที่ศึกษาที่ 10 หน้าอาคาร 3"),
]
# แก้ทั้งช่องของพรรณไม้ชนิดหนึ่ง: (รหัสชนิด, คอลัมน์, ค่าเดิม, ค่าใหม่)
FIELD_FIXES = [
    ("139", 2, "Phyllanthus acidus (L.) Skeels", "Phyllanthus amarus Schumach. & Thonn."),
    ("098", 3, "DIPTEROCARPACEAE", "LECYTHIDACEAE"),
    # พรรณไม้ใหม่ปี 59 ที่ทะเบียนยังไม่มีข้อมูล (ครูให้ค้นชื่อวิทยาศาสตร์มาใส่)
    ("202", 2, "", "Chrysopogon zizanioides (L.) Roberty"),
    ("202", 3, "", "GRAMINEAE (POACEAE)"),
    ("202", 4, "", "ไม้ล้มลุก หญ้า"),
    ("204", 2, "", "Ficus subpisocarpa Gagnep."),
    ("204", 3, "", "MORACEAE"),
    ("205", 2, "", "Schoutenia glomerata King subsp. peregrina (Craib) Roekm."),
    ("205", 3, "", "TILIACEAE (MALVACEAE)"),
    # ชื่อวิทยาศาสตร์ในทะเบียนไม่ตรงกับชื่อไทยและลักษณะเด่น (ครูให้ค้นและแก้)
    ("119", 2, "Piper aurantiacum Miq.", "Piper sarmentosum Roxb."),
    ("010", 2, "Holigarna albicans Hook.f", "Gluta usitata (Wall.) Ding Hou"),
    ("088", 2, "Justicia fragilis Wall.", "Justicia gendarussa Burm.f."),
    ("109", 2, "Millettia buteoides (Gagnep) P.K.Loc", "Millettia leucantha Kurz var. buteoides (Gagnep.) P.K.Lôc"),
    ("025", 2, "Nephrolepis sp.", "Nephrolepis cordifolia (L.) C.Presl"),
    ("179", 2, "Calamus sp.", "Calamus viminalis Willd."),
    # ลักษณะเด่นของพรรณไม้ใหม่ปี 59 (ครูให้ค้นมาใส่)
    ("202", 5, "", "ขึ้นเป็นกอแน่น ใบแคบยาวปลายแหลม รากฝอยหยั่งลึกตรงลงดิน"),
    ("204", 5, "", "ไม้ต้นผลัดใบ ผลกลมแป้นขนาดเล็ก ออกตามซอกใบหรือตามกิ่ง ผลสุกสีม่วงดำ"),
    ("205", 5, "", "ดอกสีเหลืองทอง ปลายแยก 5 แฉกคล้ายรูปดาว กลิ่นหอม บานช่วงกรกฎาคม-สิงหาคม"),
]


def clean(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def read(folder):
    files = sorted(p for p in Path(folder).glob("*.xls") if "หัวแถวทุกหน้า" not in p.name)
    if not files:
        raise SystemExit(f"ไม่พบไฟล์ .xls ใน {folder}")
    rows = []
    for p in files:
        for sh in xlrd.open_workbook(p).sheets():
            for r in range(sh.nrows):
                v = [clean(c.value) for c in sh.row(r)][:7]
                if v and v[0] in CODE_FIXES:
                    v[0] = CODE_FIXES[v[0]]
                m = CODE_RE.match(v[0]) if v else None
                if m and v[0] not in DROP_CODES and m.group(1) not in DROP_SPECIES:
                    v[3] = re.sub(r"\s*-\s*", "-", v[3])
                    v[6] = re.sub(r"พื้นที่ศึกษาที่\s*(\d+)\s*", r"พื้นที่ศึกษาที่ \1 ", v[6]).strip()
                    rows.append((int(m.group(1)), int(m.group(2) or 0), v))
    rows.sort(key=lambda x: (x[0], x[1]))
    return [v for _, _, v in rows]


def fix(rows):
    used = set()
    for v in rows:
        for i, (col, old, new) in enumerate(TEXT_FIXES):
            if old in v[col]:
                v[col] = v[col].replace(old, new)
                used.add(("t", i))
        for i, (sp, col, old, new) in enumerate(FIELD_FIXES):
            if v[0].startswith(f"7-31170-001-{sp}") and v[col] == old:
                v[col] = new
                used.add(("f", i))
    for i, f in enumerate(TEXT_FIXES):
        if ("t", i) not in used:
            print(f"หมายเหตุ: ไม่พบ {f[1]!r} ในทะเบียนนี้")
    for i, f in enumerate(FIELD_FIXES):
        if ("f", i) not in used:
            print(f"หมายเหตุ: ไม่พบ {f[2]!r} ของรหัส {f[0]} ในทะเบียนนี้")


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    rows = read(sys.argv[1])
    fix(rows)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    codes = [v[0] for v in rows]
    dups = sorted({c for c in codes if codes.count(c) > 1})
    print(f"เขียน {OUT.relative_to(ROOT)}: {len(rows)} ต้น "
          f"{len({c[:15] for c in codes})} ชนิด")
    if dups:
        print("รหัสซ้ำ:", ", ".join(dups))


if __name__ == "__main__":
    main()
