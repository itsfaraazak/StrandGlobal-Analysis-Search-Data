"""Convert note.md (simple Markdown subset) to a compact Word document.

Handles: # / ## headings, paragraphs, '- ' bullets, '1. ' numbered items,
pipe tables, **bold**, *italic*, `code`, [text](url) links.
"""
import re, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "note.md"
DST = ROOT / "Faraaz_search_web_data_note.docx"
BODY_PT, TABLE_PT = 9, 7

TOKEN = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def add_link(par, text, url, size):
    r_id = par.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                              is_external=True)
    h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), r_id)
    r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color"); c.set(qn("w:val"), "1F5FBF"); rpr.append(c)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rpr.append(u)
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); rpr.append(sz)
    r.append(rpr); t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve")
    r.append(t); h.append(r); par._p.append(h)


def add_inline(par, text, size, bold=False):
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**"):
            run = par.add_run(part[2:-2]); run.bold = True
        elif part.startswith("`"):
            run = par.add_run(part[1:-1]); run.font.name = "Menlo"
        elif part.startswith("["):
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
            add_link(par, m.group(1), m.group(2), size); continue
        elif part.startswith("*"):
            run = par.add_run(part[1:-1]); run.italic = True
        else:
            run = par.add_run(part)
        run.font.size = Pt(size)
        if bold:
            run.bold = True


def shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), hex_)
    tcPr.append(s)


def add_table(doc, rows):
    rows = [r for r in rows if not re.match(r"^\|\s*-", r)]
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    t = doc.add_table(rows=len(cells), cols=len(cells[0]))
    t.style = "Table Grid"
    for i, row in enumerate(cells):
        for j, txt in enumerate(row):
            cell = t.cell(i, j); cell.text = ""
            p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(0)
            add_inline(p, txt, TABLE_PT, bold=(i == 0 or j == 0))
            if i == 0:
                shade(cell, "DCE6F2")
    if len(cells[0]) == 4:
        for row in t.rows:
            for j, w in enumerate([2.6, 5.0, 5.0, 5.0]):
                row.cells[j].width = Cm(w)
    elif len(cells[0]) == 2:
        for row in t.rows:
            row.cells[0].width, row.cells[1].width = Cm(4.2), Cm(13.4)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.5)
    sec.top_margin = sec.bottom_margin = Cm(1.3)
    st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(BODY_PT)
    st.paragraph_format.space_after = Pt(3)

    lines = SRC.read_text().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i]); i += 1
            add_table(doc, block); continue
        if ln.startswith("# "):
            p = doc.add_paragraph(); r = p.add_run(ln[2:]); r.bold = True; r.font.size = Pt(14)
            r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        elif ln.startswith("## "):
            p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(6)
            r = p.add_run(ln[3:]); r.bold = True; r.font.size = Pt(11.5)
            r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        elif ln.startswith("- "):
            p = doc.add_paragraph(style="List Bullet"); add_inline(p, ln[2:], BODY_PT)
            p.paragraph_format.space_after = Pt(1)
        elif re.match(r"^\d+\. ", ln):
            p = doc.add_paragraph(style="List Number"); add_inline(p, re.sub(r"^\d+\. ", "", ln), BODY_PT)
            p.paragraph_format.space_after = Pt(1)
        elif ln.strip():
            p = doc.add_paragraph(); add_inline(p, ln, BODY_PT)
        i += 1
    doc.save(DST)
    print("saved", DST)


if __name__ == "__main__":
    main()
