from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "Kerlam-Mining-Services-Brochure.pdf"
HERO = ROOT / "assets" / "kerlam-quarry-hero.png"
W, H = A4

INK = colors.HexColor("#15191b")
MUTED = colors.HexColor("#5f686b")
PAPER = colors.HexColor("#f5f1e7")
WHITE = colors.white
FOREST = colors.HexColor("#244f38")
AMBER = colors.HexColor("#d18a2f")
RUST = colors.HexColor("#884931")
STONE = colors.HexColor("#d9d0c2")
CHARCOAL = colors.HexColor("#202629")


def crop_to_ratio(image, ratio):
    width, height = image.size
    current = width / height
    if current > ratio:
        new_width = int(height * ratio)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = int(width / ratio)
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def set_font(c, name, size, color=INK):
    c.setFont(name, size)
    c.setFillColor(color)


def wrap(text, font, size, max_width, c):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, font, size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def text_block(c, text, x, y, width, font="Helvetica", size=10.5, leading=14, color=MUTED):
    set_font(c, font, size, color)
    for line in wrap(text, font, size, width, c):
        c.drawString(x, y, line)
        y -= leading
    return y


def heading(c, text, x, y, width, size=28, leading=31, color=INK):
    set_font(c, "Helvetica-Bold", size, color)
    for line in wrap(text, "Helvetica-Bold", size, width, c):
        c.drawString(x, y, line)
        y -= leading
    return y


def kicker(c, text, x, y):
    set_font(c, "Helvetica-Bold", 8.5, AMBER)
    c.drawString(x, y, text.upper())


def logo(c, x, y, color=WHITE):
    c.setStrokeColor(color)
    c.setLineWidth(1.4)
    c.rect(x, y, 38, 38, stroke=1, fill=0)
    set_font(c, "Helvetica-Bold", 22, color)
    c.drawString(x + 12, y + 10, "K")
    set_font(c, "Helvetica-Bold", 15, color)
    c.drawString(x + 50, y + 22, "Kerlam")
    set_font(c, "Helvetica", 9.5, color)
    c.drawString(x + 50, y + 8, "Mining Services")


def service_card(c, x, y, w, h, number, title, body):
    c.setFillColor(WHITE)
    c.setStrokeColor(STONE)
    c.rect(x, y, w, h, stroke=1, fill=1)
    c.setFillColor(FOREST)
    c.rect(x + 18, y + h - 48, 32, 32, stroke=0, fill=1)
    set_font(c, "Helvetica-Bold", 9, WHITE)
    c.drawString(x + 27, y + h - 36, number)
    set_font(c, "Helvetica-Bold", 14, INK)
    c.drawString(x + 18, y + h - 76, title)
    text_block(c, body, x + 18, y + h - 98, w - 36, size=9.8, leading=14)


def page_background(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)


def build():
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("Kerlam Mining Services Brochure")
    c.setAuthor("Kerlam Mining Services")

    hero = Image.open(HERO).convert("RGB")
    cover_crop = crop_to_ratio(hero, W / 480)
    hero_reader = ImageReader(cover_crop)

    c.drawImage(hero_reader, 0, H - 480, width=W, height=480)
    c.setFillColor(CHARCOAL)
    c.rect(0, 0, W, 390, stroke=0, fill=1)
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.22))
    c.rect(0, H - 480, W, 480, stroke=0, fill=1)
    logo(c, 54, H - 92)
    kicker(c, "Quarry mining contracts across Kerala", 54, 318)
    y = heading(c, "Mining, crusher support, and licensed explosives supply.", 54, 282, 470, 34, 37, WHITE)
    text_block(
        c,
        "Reliable field teams for stone quarries and stone crushers, built around production planning, safety discipline, and statewide service coverage.",
        54,
        y - 12,
        430,
        size=14,
        leading=20,
        color=colors.HexColor("#e8e7e1"),
    )
    c.showPage()

    page_background(c)
    kicker(c, "Company overview", 54, 770)
    y = heading(c, "Practical quarry support from planning to production.", 54, 735, 430)
    text_block(
        c,
        "Kerlam Mining Services works with quarry owners, stone crusher units, and aggregate suppliers throughout Kerala. We support approved quarry operations with mining contracts, machinery coordination, crusher feed planning, and compliant explosives supply.",
        54,
        y - 18,
        310,
        size=11.5,
        leading=16,
    )
    c.setFillColor(FOREST)
    c.rect(392, 594, 145, 116, stroke=0, fill=1)
    set_font(c, "Helvetica-Bold", 22, WHITE)
    c.drawString(410, 660, "Kerala-wide")
    text_block(c, "Service coverage for stone quarry and crusher operations.", 410, 635, 105, size=10.2, leading=14, color=colors.HexColor("#e9eee7"))
    service_card(c, 54, 390, 235, 155, "01", "Mining Contracts", "Contract mining support for quarry benches, loading plans, output targets, and daily site coordination.")
    service_card(c, 306, 390, 235, 155, "02", "Stone Crusher Support", "Crusher feed management, stone movement, stockyard planning, and quarry-to-crusher workflow support.")
    service_card(c, 54, 210, 235, 155, "03", "Explosives Supply", "Licensed explosives supply for eligible quarries and crushers with documentation and controlled handling.")
    service_card(c, 306, 210, 235, 155, "04", "Machinery Coordination", "Coordination for excavators, loaders, tippers, compressors, and quarry equipment based on site needs.")
    set_font(c, "Helvetica-Bold", 10, FOREST)
    c.drawString(54, 54, "Kerlam Mining Services")
    set_font(c, "Helvetica", 8.5, MUTED)
    c.drawString(54, 38, "Mining contracts | Crusher support | Licensed explosives supply")
    c.showPage()

    page_background(c)
    kicker(c, "Operations and safety", 54, 770)
    y = heading(c, "Safe systems for dependable production.", 54, 735, 430)
    set_font(c, "Helvetica-Bold", 15, INK)
    c.drawString(54, y - 14, "How we support sites")
    bullets = [
        "Site visits to understand quarry layout, access roads, and crusher capacity.",
        "Production planning for stone movement, bench work, and crusher feed continuity.",
        "Coordination of field teams, equipment, and approved blasting requirements.",
        "Responsive support during monsoon conditions and changing site demands.",
    ]
    by = y - 42
    for item in bullets:
        c.setFillColor(AMBER)
        c.circle(60, by + 5, 2.4, stroke=0, fill=1)
        by = text_block(c, item, 72, by + 10, 260, size=10.8, leading=15) - 7

    c.setFillColor(CHARCOAL)
    c.rect(372, 474, 169, 190, stroke=0, fill=1)
    set_font(c, "Helvetica-Bold", 15, WHITE)
    c.drawString(392, 625, "Compliance first")
    text_block(
        c,
        "Explosives support is provided only for approved quarry operations through licensed supply channels and required documentation. Work is planned with controlled access, trained supervision, and strict safety procedures.",
        392,
        596,
        124,
        size=10.2,
        leading=15,
        color=colors.HexColor("#e3e3de"),
    )

    c.setFillColor(colors.HexColor("#e4ded1"))
    c.rect(54, 330, 487, 104, stroke=0, fill=1)
    c.setFillColor(RUST)
    c.rect(54, 330, 12, 104, stroke=0, fill=1)
    set_font(c, "Helvetica-Bold", 15, INK)
    c.drawString(84, 396, "Serving Kerala")
    text_block(
        c,
        "Supporting quarry and crusher operations across major production districts including Kasaragod, Kannur, Kozhikode, Malappuram, Thrissur, Ernakulam, Kottayam, Idukki, Kollam, and Thiruvananthapuram.",
        84,
        369,
        410,
        size=10.6,
        leading=15,
    )

    c.setStrokeColor(STONE)
    c.line(54, 230, 541, 230)
    kicker(c, "For enquiries", 54, 195)
    set_font(c, "Helvetica-Bold", 24, INK)
    c.drawString(54, 160, "Request a site visit")
    text_block(c, "Share your quarry location, crusher capacity, production requirement, and license status.", 54, 130, 270, size=10.8, leading=15)
    c.setFillColor(FOREST)
    c.rect(356, 86, 185, 108, stroke=0, fill=1)
    set_font(c, "Helvetica-Bold", 14, WHITE)
    c.drawString(376, 158, "Kerlam Mining Services")
    text_block(c, "Mining contracts | Crusher support | Licensed explosives supply", 376, 134, 140, size=9.5, leading=13, color=colors.HexColor("#e9eee7"))
    set_font(c, "Helvetica", 10, colors.HexColor("#e9eee7"))
    c.drawString(376, 95, "Kerala, India")
    c.showPage()

    c.save()
    print(OUT)


if __name__ == "__main__":
    build()
