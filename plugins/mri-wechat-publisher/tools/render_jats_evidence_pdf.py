import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer


XLINK = "{http://www.w3.org/1999/xlink}href"


def clean_text(node):
    if node is None:
        return ""
    value = " ".join("".join(node.itertext()).split())
    value = value.replace("−", "-").replace("–", "-").replace("—", "-")
    return value


def safe_markup(value):
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\s+", " ", value).strip()


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("NotoSansSC", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(A4[0] / 2, 10 * mm, f"Internal evidence rendering - page {doc.page}")
    canvas.restoreState()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_xml", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--figure-dir", type=Path)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()

    root = ET.parse(args.input_xml).getroot()
    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("NotoSansSC", str(args.font.resolve())))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleLocal", parent=styles["Title"], fontName="NotoSansSC", fontSize=18,
        leading=24, alignment=TA_CENTER, spaceAfter=10 * mm,
    )
    meta_style = ParagraphStyle(
        "MetaLocal", parent=styles["BodyText"], fontName="NotoSansSC", fontSize=9,
        leading=13, textColor=colors.HexColor("#555555"), spaceAfter=2 * mm,
    )
    body_style = ParagraphStyle(
        "BodyLocal", parent=styles["BodyText"], fontName="NotoSansSC", fontSize=9.2,
        leading=13.8, spaceAfter=3.5 * mm,
    )
    h1_style = ParagraphStyle(
        "H1Local", parent=styles["Heading1"], fontName="NotoSansSC", fontSize=14,
        leading=18, spaceBefore=6 * mm, spaceAfter=3 * mm, textColor=colors.HexColor("#1f4e79"),
    )
    h2_style = ParagraphStyle(
        "H2Local", parent=styles["Heading2"], fontName="NotoSansSC", fontSize=11.5,
        leading=15, spaceBefore=4 * mm, spaceAfter=2 * mm, textColor=colors.HexColor("#2f5597"),
    )
    caption_style = ParagraphStyle(
        "CaptionLocal", parent=body_style, fontSize=8.3, leading=12,
        textColor=colors.HexColor("#444444"), leftIndent=4 * mm, rightIndent=4 * mm,
    )

    doc = SimpleDocTemplate(
        str(args.output_pdf.resolve()), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=clean_text(root.find(".//article-meta/title-group/article-title")),
        author="Locally rendered from Europe PMC Version of Record JATS XML",
    )
    story = []
    title = clean_text(root.find(".//article-meta/title-group/article-title"))
    journal = clean_text(root.find(".//journal-meta/journal-title-group/journal-title"))
    doi = ""
    pmid = ""
    for node in root.findall(".//article-meta/article-id"):
        if node.attrib.get("pub-id-type") == "doi":
            doi = clean_text(node)
        if node.attrib.get("pub-id-type") == "pmid":
            pmid = clean_text(node)
    pub_date = root.find(".//article-meta/pub-date")
    date_value = "-".join(
        filter(None, [clean_text(pub_date.find("year")) if pub_date is not None else "",
                      clean_text(pub_date.find("month")) if pub_date is not None else "",
                      clean_text(pub_date.find("day")) if pub_date is not None else ""])
    )
    authors = []
    for contrib in root.findall(".//article-meta/contrib-group/contrib"):
        name = contrib.find("name")
        collab = clean_text(contrib.find("collab"))
        if collab:
            authors.append(collab)
        elif name is not None:
            authors.append(" ".join(filter(None, [clean_text(name.find("given-names")), clean_text(name.find("surname"))])))

    story.append(Paragraph(safe_markup(title), title_style))
    story.append(Paragraph(safe_markup(", ".join(authors)), meta_style))
    story.append(Paragraph(safe_markup(f"{journal} | DOI: {doi} | PMID: {pmid} | Publication date: {date_value}"), meta_style))
    story.append(Paragraph(
        "Locally rendered from the Europe PMC Version of Record JATS XML for internal evidence validation. "
        "This is not the publisher-designed PDF. Scientific text and identifiers derive from the registered VOR XML.",
        meta_style,
    ))

    abstract = root.find(".//article-meta/abstract")
    if abstract is not None:
        story.append(Paragraph("ABSTRACT", h1_style))
        story.append(Paragraph(safe_markup(clean_text(abstract)), body_style))

    figure_dir = args.figure_dir.resolve() if args.figure_dir else None

    def render_section(section, depth=1):
        heading = clean_text(section.find("title"))
        if heading:
            story.append(Paragraph(safe_markup(heading), h1_style if depth == 1 else h2_style))
        for child in list(section):
            tag = child.tag.split("}")[-1]
            if tag == "title":
                continue
            if tag == "p":
                paragraph = clean_text(child)
                if paragraph:
                    story.append(Paragraph(safe_markup(paragraph), body_style))
            elif tag == "sec":
                render_section(child, depth + 1)
            elif tag == "fig":
                label = clean_text(child.find("label"))
                caption = clean_text(child.find("caption"))
                href = ""
                graphic = child.find(".//graphic")
                if graphic is not None:
                    href = graphic.attrib.get(XLINK, "")
                local = figure_dir / Path(href).name if figure_dir and href else None
                if local and local.is_file():
                    image = Image(str(local))
                    max_width = 168 * mm
                    max_height = 190 * mm
                    scale = min(max_width / image.imageWidth, max_height / image.imageHeight, 1)
                    image.drawWidth = image.imageWidth * scale
                    image.drawHeight = image.imageHeight * scale
                    story.append(Spacer(1, 2 * mm))
                    story.append(image)
                if label or caption:
                    story.append(Paragraph(safe_markup(f"{label}. {caption}".strip(". ")), caption_style))
            elif tag == "table-wrap":
                label = clean_text(child.find("label"))
                caption = clean_text(child.find("caption"))
                if label or caption:
                    story.append(Paragraph(safe_markup(f"{label}. {caption}".strip(". ")), caption_style))
                for row in child.findall(".//tr"):
                    cells = [clean_text(cell) for cell in list(row)]
                    if any(cells):
                        story.append(Paragraph(safe_markup(" | ".join(cells)), caption_style))
            elif tag in {"list", "disp-quote", "boxed-text"}:
                value = clean_text(child)
                if value:
                    story.append(Paragraph(safe_markup(value), body_style))

    for section in root.findall("./body/sec"):
        render_section(section)

    refs = root.findall(".//ref-list/ref")
    if refs:
        story.append(PageBreak())
        story.append(Paragraph("REFERENCES", h1_style))
        for ref in refs:
            label = clean_text(ref.find("label"))
            citation = clean_text(ref.find("mixed-citation")) or clean_text(ref.find("element-citation"))
            if citation:
                story.append(Paragraph(safe_markup(f"{label}. {citation}".strip(". ")), caption_style))

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    print(str(args.output_pdf.resolve()))


if __name__ == "__main__":
    main()
