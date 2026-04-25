from pathlib import Path
from models.schemas import MeetingSummary
from utils.logger import get_logger

logger = get_logger("export")
OUTPUTS_DIR = Path("outputs")

def save_transcript(transcript: str, filename: str) -> Path:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    stem = Path(filename).stem
    output_path = OUTPUTS_DIR / f"{stem}_transcript.txt"
    output_path.write_text(transcript, encoding="utf-8")
    logger.info(f"Transcript disimpan: {output_path}")
    return output_path

def save_summary(summary: MeetingSummary, filename: str) -> Path:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    stem = Path(filename).stem
    output_path = OUTPUTS_DIR / f"{stem}_summary.md"

    lines = [f"# Ringkasan Meeting — {stem}\n"]
    lines.append(f"## Ringkasan\n\n{summary.summary}\n")

    if summary.topics_discussed:
        lines.append("## Topik yang Dibahas\n")
        for topic in summary.topics_discussed:
            lines.append(f"- {topic}")
        lines.append("")

    if summary.key_decisions:
        lines.append("## Keputusan Penting\n")
        for decision in summary.key_decisions:
            lines.append(f"- {decision}")
        lines.append("")

    if summary.action_items:
        lines.append("## Action Items\n")
        for item in summary.action_items:
            assignee = f" — {item.assignee}" if item.assignee else ""
            priority_label = {
                "high": "High", "medium": "Medium", "low": "Low"
            }.get(item.priority, item.priority)
            lines.append(f"- [{priority_label}]{assignee}: {item.task}")
    else:
        lines.append("## Action Items\n\nTidak ada action items yang terdeteksi.")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Summary markdown disimpan: {output_path}")
    return output_path

def save_summary_pdf(summary: MeetingSummary, filename: str) -> Path:
    from fpdf import FPDF

    OUTPUTS_DIR.mkdir(exist_ok=True)
    stem = Path(filename).stem
    output_path = OUTPUTS_DIR / f"{stem}_summary.pdf"

    def clean(text: str) -> str:
        replacements = {
            "—": "-", "–": "-", "\u2019": "'", "\u2018": "'",
            "\u201c": '"', "\u201d": '"', "…": "...", "\u2022": "-",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        # Hapus karakter non-latin yang tersisa
        return text.encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    page_width = pdf.w - 40  # 210 - 40mm margin

    def heading(text: str, size: int = 13):
        pdf.set_font("Helvetica", "B", size)
        pdf.cell(page_width, 8, clean(text), ln=True)
        pdf.ln(2)

    def body(text: str):
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(page_width, 6, clean(text))
        pdf.ln(2)

    def bullet(text: str):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(25)
        pdf.multi_cell(page_width - 5, 6, clean(f"- {text}"))

    def divider():
        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(4)

    # Judul
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(page_width, 10, clean(f"Meeting Summary - {stem[:50]}"), ln=True)
    divider()

    # Ringkasan
    heading("Ringkasan")
    body(summary.summary)
    pdf.ln(2)

    # Topik
    if summary.topics_discussed:
        divider()
        heading("Topik yang Dibahas")
        for topic in summary.topics_discussed:
            bullet(topic)
        pdf.ln(2)

    # Keputusan
    if summary.key_decisions:
        divider()
        heading("Keputusan Penting")
        for decision in summary.key_decisions:
            bullet(decision)
        pdf.ln(2)

    # Action items
    divider()
    heading("Action Items")
    if summary.action_items:
        for item in summary.action_items:
            assignee = f" ({clean(item.assignee)})" if item.assignee else ""
            priority = item.priority.upper()
            bullet(f"[{priority}]{assignee}: {item.task}")
    else:
        body("Tidak ada action items yang terdeteksi.")

    pdf.output(str(output_path))
    logger.info(f"Summary PDF disimpan: {output_path}")
    return output_path