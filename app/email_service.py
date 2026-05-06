import smtplib
import re
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, KeepTogether
)

load_dotenv()

PAGE_W, PAGE_H = A4
MARGIN_L = 2.2 * cm
MARGIN_R = 2.2 * cm
MARGIN_T = 3.2 * cm
MARGIN_B = 2.2 * cm

NAVY      = colors.HexColor("#0D1B2A")
DARK_BLUE = colors.HexColor("#1E3A5F")
MID_BLUE  = colors.HexColor("#2E6DB4")
WHITE     = colors.white
GRAY_TXT  = colors.HexColor("#374151")
GRAY_SUB  = colors.HexColor("#6B7280")
GRAY_MID  = colors.HexColor("#E5E7EB")


# ══════════════════════════════════════════════
#  SANITIZER — cleans Groq output before PDF
# ══════════════════════════════════════════════
def sanitize_markdown(text: str) -> str:
    """Convert any * or ** bullets/markers Groq produces into clean dashes."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()

        # "** text" bullet → "- text"
        if re.match(r'^\*\*\s+', stripped):
            line = "- " + stripped[3:].strip()

        # "* text" bullet → "- text"
        elif re.match(r'^\*\s+', stripped):
            line = "- " + stripped[2:].strip()

        # Remove leftover **bold** markers from non-bullet lines
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)

        # Remove leftover *italic* markers from non-bullet lines
        if not line.strip().startswith("- "):
            line = re.sub(r'\*(.*?)\*', r'\1', line)

        lines.append(line)
    return "\n".join(lines)


# ══════════════════════════════════════════════
#  HEADER & FOOTER — runs on every page
# ══════════════════════════════════════════════
class HeaderFooter:
    def __init__(self, topic: str):
        self.topic = topic
        self.date  = datetime.now().strftime("%B %d, %Y")

    def draw(self, canv, doc):
        canv.saveState()
        w, h = A4

        # Navy header band
        canv.setFillColor(NAVY)
        canv.rect(0, h - 2.4*cm, w, 2.4*cm, fill=1, stroke=0)

        # Dark-blue left accent stripe
        canv.setFillColor(DARK_BLUE)
        canv.rect(0, h - 2.4*cm, 0.5*cm, 2.4*cm, fill=1, stroke=0)

        # App name
        canv.setFont("Helvetica-Bold", 11)
        canv.setFillColor(WHITE)
        canv.drawString(0.9*cm, h - 1.3*cm, "AI Research Agent")

        # Pipe separator
        canv.setFont("Helvetica", 10)
        canv.setFillColor(colors.HexColor("#4B6A8A"))
        canv.drawString(0.9*cm + 118, h - 1.3*cm, "|")

        # Topic
        topic_display = (self.topic if len(self.topic) <= 58
                         else self.topic[:55] + "...")
        canv.setFont("Helvetica", 9)
        canv.setFillColor(colors.HexColor("#93B8D8"))
        canv.drawString(0.9*cm + 130, h - 1.3*cm, topic_display)

        # Date right
        canv.setFont("Helvetica", 8)
        canv.setFillColor(colors.HexColor("#7A9ABB"))
        canv.drawRightString(w - 0.8*cm, h - 1.3*cm, self.date)

        # Header bottom border
        canv.setStrokeColor(MID_BLUE)
        canv.setLineWidth(1.2)
        canv.line(0, h - 2.4*cm, w, h - 2.4*cm)

        # Footer separator line
        canv.setStrokeColor(GRAY_MID)
        canv.setLineWidth(0.5)
        canv.line(MARGIN_L, 1.55*cm, w - MARGIN_R, 1.55*cm)

        # Footer left
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(GRAY_SUB)
        canv.drawString(MARGIN_L, 1.05*cm, "Auto-generated")

        # Footer center
        canv.setFont("Helvetica-Bold", 8)
        canv.setFillColor(DARK_BLUE)
        canv.drawCentredString(w / 2, 1.05*cm, "AI Research Agent")

        # Footer right — page number
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(GRAY_SUB)
        canv.drawRightString(w - MARGIN_R, 1.05*cm, f"Page {doc.page}")

        canv.restoreState()


# ══════════════════════════════════════════════
#  STYLES
# ══════════════════════════════════════════════
def make_styles():
    return {
        "report_label": ParagraphStyle("RL",
            fontSize=7.5, fontName="Helvetica-Bold",
            textColor=MID_BLUE, spaceAfter=4, leading=10),

        "report_title": ParagraphStyle("RT",
            fontSize=22, fontName="Helvetica-Bold",
            textColor=NAVY, spaceAfter=5, leading=28),

        "subtitle": ParagraphStyle("ST",
            fontSize=10, fontName="Helvetica",
            textColor=GRAY_SUB, spaceAfter=18, leading=14),

        "h2": ParagraphStyle("H2",
            fontSize=13, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, spaceBefore=6,
            spaceAfter=5, leading=18),

        "h3": ParagraphStyle("H3",
            fontSize=11, fontName="Helvetica-Bold",
            textColor=MID_BLUE, spaceBefore=8,
            spaceAfter=4, leading=15),

        "body": ParagraphStyle("Body",
            fontSize=9.5, fontName="Helvetica",
            textColor=GRAY_TXT, spaceAfter=7,
            leading=15.5, alignment=TA_JUSTIFY),

        "bullet": ParagraphStyle("Bul",
            fontSize=9.5, fontName="Helvetica",
            textColor=GRAY_TXT, spaceAfter=5,
            leading=14.5, leftIndent=16),
    }


# ══════════════════════════════════════════════
#  SECTION HEADING
# ══════════════════════════════════════════════
def section_heading(title: str, S: dict):
    return KeepTogether([
        Spacer(1, 10),
        Paragraph(title, S["h2"]),
        HRFlowable(width="100%", thickness=1.0,
                   color=MID_BLUE, spaceAfter=7),
    ])


# ══════════════════════════════════════════════
#  PDF GENERATOR
# ══════════════════════════════════════════════
def generate_pdf_report(topic: str, report_content: str) -> bytes:
    """Convert markdown report into a clean professional PDF."""

    # Clean Groq output first — removes all * and ** symbols
    report_content = sanitize_markdown(report_content)

    buffer = BytesIO()
    S      = make_styles()
    hf     = HeaderFooter(topic)

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T,  bottomMargin=MARGIN_B,
        title=f"Research Report: {topic}",
        author="AI Research Agent",
    )

    story = []

    # Title block
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("RESEARCH REPORT", S["report_label"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(topic.title(), S["report_title"]))
    story.append(Paragraph(
        "Automated research compiled and structured by AI Research Agent.",
        S["subtitle"]
    ))
    # Clean divider — no meta bar
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=GRAY_MID, spaceAfter=8
    ))

    # Parse markdown
    bullet_buf = []

    def flush_bullets():
        for b in bullet_buf:
            story.append(b)
        bullet_buf.clear()

    for raw in report_content.split("\n"):
        line = raw.strip()

        if not line:
            flush_bullets()
            story.append(Spacer(1, 3))
            continue

        # H1 — skip, rendered as title above
        if line.startswith("# ") and not line.startswith("## "):
            continue

        # H2 — section heading
        elif line.startswith("## "):
            flush_bullets()
            story.append(section_heading(line[3:].strip(), S))

        # H3
        elif line.startswith("### "):
            flush_bullets()
            story.append(Paragraph(line[4:].strip(), S["h3"]))

        # Bullet — dark navy square
        elif line.startswith("- "):
            text = line[2:].strip()
            bullet_buf.append(Paragraph(
                f'<font color="#1E3A5F">■</font>&nbsp;&nbsp;{text}',
                S["bullet"]
            ))

        # Divider
        elif line == "---":
            flush_bullets()
            story.append(HRFlowable(
                width="100%", thickness=0.4,
                color=GRAY_MID, spaceAfter=6
            ))

        # Skip any remaining italic footer lines
        elif re.match(r'^\*[^*]+\*$', line):
            continue

        # Normal paragraph
        else:
            flush_bullets()
            story.append(Paragraph(line, S["body"]))

    flush_bullets()
    doc.build(story, onFirstPage=hf.draw, onLaterPages=hf.draw)
    return buffer.getvalue()


# ══════════════════════════════════════════════
#  EMAIL SENDER
# ══════════════════════════════════════════════
def send_report_email(topic: str, report_content: str, recipient: str) -> bool:
    """Generate PDF and send as email attachment via Gmail SMTP."""
    sender   = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password]):
        print("Email credentials not configured.")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Research Report: {topic}"
        msg["From"]    = f"AI Research Agent <{sender}>"
        msg["To"]      = recipient

        # Plain text email body
        body = MIMEText(f"""Hello,

Please find attached the AI Research Report for:

  "{topic}"

The report covers:
  - Executive Summary
  - Key Findings
  - Detailed Analysis
  - Current Trends
  - Conclusion

Regards,
AI Research Agent
""", "plain", "utf-8")
        msg.attach(body)

        # Generate and attach PDF
        pdf_bytes = generate_pdf_report(topic, report_content)
        safe_name = re.sub(r'[^\w\s-]', '', topic)[:50].strip().replace(' ', '_')
        filename  = f"Research_Report_{safe_name}.pdf"

        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"'
        )
        msg.attach(part)

        # Send via Gmail SMTP SSL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        print(f"PDF report emailed successfully to {recipient}")
        return True

    except Exception as e:
        print(f"Email failed: {str(e)}")
        return False