"""Export the revised Chinese report with standard-library OOXML APIs."""

from pathlib import Path
import argparse
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs/REPORT_20261029.md"
OUTPUT = Path(__file__).resolve().parent / "贴地飞行第二部分进度汇报2026-10-30.docx"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def node(parent, tag, text=None, **attrs):
    prefix, local = tag.split(":")
    element = ET.SubElement(parent, "{%s}%s" % (NS[prefix], local))
    for key, value in attrs.items():
        if ":" in key:
            ap, ak = key.split(":")
            key = "{%s}%s" % (NS[ap], ak)
        element.set(key, str(value))
    if text is not None:
        element.text = text
    return element


def paragraph(parent, text="", style="Normal", page_break=False):
    p = node(parent, "w:p")
    props = node(p, "w:pPr")
    node(props, "w:pStyle", **{"w:val": style})
    if page_break:
        node(props, "w:pageBreakBefore")
    if text:
        run = node(p, "w:r")
        node(run, "w:t", text)
    return p


def styles(flow=False):
    root = ET.Element("{%s}styles" % NS["w"])
    defaults = node(root, "w:docDefaults")
    rp = node(node(defaults, "w:rPrDefault"), "w:rPr")
    node(rp, "w:rFonts", **{"w:ascii": "Times New Roman", "w:hAnsi": "Times New Roman", "w:eastAsia": "宋体"})
    node(rp, "w:sz", **{"w:val": 24})
    node(rp, "w:lang", **{"w:val": "en-US", "w:eastAsia": "zh-CN"})
    definitions = [
        ("Normal", 26, False, "both", 520, 100, 520),
        ("Opening", 24, False, "both", 440, 100, 480),
        ("Compact", 24, False, "both", 420, 100, 480),
        ("Title", 30, True, "center", 400, 200, 0),
        ("Heading1", 30, False, "left", 400, 160, 0),
        ("Heading2", 28, True, "left", 380, 160, 0),
        ("Heading3", 26, True, "left", 360, 180, 0),
        ("Caption", 21, False, "center", 290, 120, 0),
        ("Image", 20, False, "center", 240, 80, 0),
        ("Table", 24, False, "left", 380, 0, 0),
        ("Footer", 20, False, "center", 240, 0, 0),
    ]
    if flow:
        definitions[0] = ("Normal", 28, False, "both", 640, 120, 560)
        definitions[3] = ("Title", 34, True, "center", 460, 240, 0)
        definitions[4] = ("Heading1", 32, False, "left", 460, 200, 0)
    for name, size, bold, align, line, after, indent in definitions:
        s = node(root, "w:style", **{"w:type": "paragraph", "w:styleId": name})
        if name == "Normal":
            s.set("{%s}default" % NS["w"], "1")
        node(s, "w:name", **{"w:val": name})
        pp = node(s, "w:pPr")
        node(pp, "w:spacing", **{"w:line": line, "w:lineRule": "atLeast" if name == "Image" else "exact", "w:after": after})
        node(pp, "w:jc", **{"w:val": align})
        node(pp, "w:ind", **{"w:firstLine": indent})
        node(pp, "w:widowControl")
        if name.startswith("Heading") or name == "Image":
            node(pp, "w:keepNext")
        if name.startswith("Heading"):
            node(pp, "w:outlineLvl", **{"w:val": int(name[-1]) - 1})
            if flow:
                pp.find("w:spacing", NS).set("{%s}before" % NS["w"], "240")
        rp = node(s, "w:rPr")
        node(rp, "w:sz", **{"w:val": size})
        node(rp, "w:szCs", **{"w:val": size})
        if bold:
            node(rp, "w:b")
        if name in {"Title", "Heading1", "Heading2", "Heading3"}:
            node(rp, "w:rFonts", **{"w:eastAsia": "黑体"})
    return root


def table(parent, lines):
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    t = node(parent, "w:tbl")
    props = node(t, "w:tblPr")
    node(props, "w:tblW", **{"w:w": 9637, "w:type": "dxa"})
    node(props, "w:tblLayout", **{"w:type": "fixed"})
    borders = node(props, "w:tblBorders")
    for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        node(borders, "w:" + edge, **{"w:val": "single", "w:sz": 4, "w:color": "C3C9CE"})
    margins = node(props, "w:tblCellMar")
    for edge in ["top", "bottom", "left", "right"]:
        node(margins, "w:" + edge, **{"w:w": 90, "w:type": "dxa"})
    grid = node(t, "w:tblGrid")
    widths = [2300, 7337]
    for width in widths:
        node(grid, "w:gridCol", **{"w:w": width})
    for index, row in enumerate(rows):
        tr = node(t, "w:tr")
        trp = node(tr, "w:trPr")
        node(trp, "w:cantSplit")
        if index == 0:
            node(trp, "w:tblHeader")
        for col, text in enumerate(row):
            tc = node(tr, "w:tc")
            tcp = node(tc, "w:tcPr")
            node(tcp, "w:tcW", **{"w:w": widths[col], "w:type": "dxa"})
            node(tcp, "w:vAlign", **{"w:val": "center"})
            if index == 0:
                node(tcp, "w:shd", **{"w:fill": "EDEFF1"})
            p = paragraph(tc, text, "Table")
            if index == 0:
                run = p.find("w:r", NS)
                run_props = ET.Element("{%s}rPr" % NS["w"])
                run.insert(0, run_props)
                node(run_props, "w:b")
    paragraph(parent, "", "Table")


def picture(parent, path, caption, index, double=False, flow=False):
    width, height = Image.open(path).size
    max_width = 4_530_000 if double else 6_119_495
    max_height = (2_725_000 if double else 3_300_000) if width > height * 1.2 else 2_900_000
    if path.name=='motion-observations.png':
        max_height=7_000_000
    elif path.name in ('elevation-map.png','elevation-rviz.png'):
        max_height=4_300_000
    if flow:
        max_width = 6_119_495
        max_height = 7_000_000 if path.name == 'motion-observations.png' else 4_800_000
    scale = min(max_width / width, max_height / height)
    cx, cy = int(width * scale), int(height * scale)
    p = paragraph(parent, style="Image")
    inline = node(node(node(p, "w:r"), "w:drawing"), "wp:inline", distT=0, distB=0, distL=0, distR=0)
    node(inline, "wp:extent", cx=cx, cy=cy)
    node(inline, "wp:docPr", id=index, name="Figure %d" % index, descr=caption)
    graphic = node(inline, "a:graphic")
    data = node(graphic, "a:graphicData", uri=NS["pic"])
    pic = node(data, "pic:pic")
    nv = node(pic, "pic:nvPicPr")
    node(nv, "pic:cNvPr", id=index, name=path.name)
    node(nv, "pic:cNvPicPr")
    fill = node(pic, "pic:blipFill")
    node(fill, "a:blip", **{"r:embed": "rIdImage%d" % index})
    node(node(fill, "a:stretch"), "a:fillRect")
    sp = node(pic, "pic:spPr")
    transform = node(sp, "a:xfrm")
    node(transform, "a:off", x=0, y=0)
    node(transform, "a:ext", cx=cx, cy=cy)
    node(node(sp, "a:prstGeom", prst="rect"), "a:avLst")


def xml(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--flow-layout', action='store_true', help='Use continuous body text within each main direction.')
    parser.add_argument('--page-count', type=int, help='Set document metadata to the verified PDF page count.')
    args=parser.parse_args()
    output=(args.output_dir/OUTPUT.name) if args.output_dir else OUTPUT
    output.parent.mkdir(parents=True,exist_ok=True)
    source = args.source.resolve()
    content = source.read_text()
    pages = content.split("<!-- pagebreak -->")
    document = ET.Element("{%s}document" % NS["w"])
    body = node(document, "w:body")
    images = []
    for page_index, section in enumerate(pages):
        lines = section.strip().splitlines()
        i = 0
        first = True
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("|"):
                group = []
                while i < len(lines) and lines[i].startswith("|"):
                    group.append(lines[i])
                    i += 1
                table(body, group)
                continue
            match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
            if match:
                alt, relative = match.groups()
                path = (source.parent / relative).resolve()
                images.append(path)
                picture(body, path, alt, len(images), section.count("![") > 1, args.flow_layout)
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                style = {1: "Title", 2: "Heading1", 3: "Heading2", 4: "Heading3"}[level]
                page_break = False if args.flow_layout else page_index > 0 and first
                paragraph(body, line[level:].strip(), style, page_break)
            else:
                normal_style = "Opening" if page_index == 0 else "Compact" if section.count("![") > 1 else "Normal"
                if args.flow_layout:
                    normal_style = "Normal"
                paragraph(body, line, "Caption" if re.match(r"图\d+[a-z]? ", line) else normal_style)
            first = False
            i += 1
    section = node(body, "w:sectPr")
    node(section, "w:footerReference", **{"w:type": "default", "r:id": "rIdFooter"})
    node(section, "w:pgSz", **{"w:w": 11906, "w:h": 16838})
    node(section, "w:pgMar", **{"w:top": 1418, "w:right": 851, "w:bottom": 851, "w:left": 1418, "w:header": 500, "w:footer": 450})
    footer = ET.Element("{%s}ftr" % NS["w"])
    p = paragraph(footer, style="Footer")
    node(node(p, "w:r"), "w:t", "— ")
    field = node(p, "w:fldSimple", **{"w:instr": "PAGE"})
    node(node(field, "w:r"), "w:t", "1")
    node(node(p, "w:r"), "w:t", " —")

    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    rels = ET.Element("Relationships", xmlns=rel_ns)
    for ident, kind, target in [("rIdStyles", "styles", "styles.xml"), ("rIdFooter", "footer", "footer1.xml")]:
        ET.SubElement(rels, "Relationship", Id=ident, Type=NS["r"] + "/" + kind, Target=target)
    for index in range(1, len(images) + 1):
        ET.SubElement(rels, "Relationship", Id="rIdImage%d" % index, Type=NS["r"] + "/image", Target="media/image%d.png" % index)
    types = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    for extension, mime in [("rels", "application/vnd.openxmlformats-package.relationships+xml"), ("xml", "application/xml"), ("png", "image/png")]:
        ET.SubElement(types, "Default", Extension=extension, ContentType=mime)
    for part, mime in [("document", "document.main"), ("styles", "styles"), ("footer1", "footer")]:
        ET.SubElement(types, "Override", PartName="/word/%s.xml" % part, ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.%s+xml" % mime)
    ET.SubElement(types, "Override", PartName="/docProps/app.xml", ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml")
    ET.SubElement(types, "Override", PartName="/docProps/core.xml", ContentType="application/vnd.openxmlformats-package.core-properties+xml")
    package_rels = ET.Element("Relationships", xmlns=rel_ns)
    for ident, kind, target in [("rId1", NS["r"] + "/officeDocument", "word/document.xml"), ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"), ("rId3", NS["r"] + "/extended-properties", "docProps/app.xml")]:
        ET.SubElement(package_rels, "Relationship", Id=ident, Type=kind, Target=target)
    app = ET.Element("Properties", xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties")
    if args.page_count is not None or not args.flow_layout:
        ET.SubElement(app, "Pages").text = str(args.page_count if args.page_count is not None else len(pages))
    ET.SubElement(app, "Application").text = "UAV-FusionMap Report"
    core = ET.Element("{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}coreProperties")
    ET.SubElement(core, "{http://purl.org/dc/elements/1.1/}title").text = "贴地飞行第二部分进度汇报2026-10-30"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, element in [("[Content_Types].xml", types), ("_rels/.rels", package_rels), ("word/document.xml", document), ("word/styles.xml", styles(args.flow_layout)), ("word/_rels/document.xml.rels", rels), ("word/footer1.xml", footer), ("docProps/app.xml", app), ("docProps/core.xml", core)]:
            archive.writestr(name, xml(element))
        for index, path in enumerate(images, 1):
            archive.write(path, "word/media/image%d.png" % index)
    print(output)
    print("Sections: %d; figures: %d; characters: %d" % (len(pages), len(images), len(content)))


if __name__ == "__main__":
    main()
