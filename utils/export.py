from pathlib import Path
from models.schemas import MeetingSummary

OUTPUTS_DIR = Path("outputs")

def save_transcript(transcript: str, filename: str) -> Path:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    stem = Path(filename).stem
    output_path = OUTPUTS_DIR / f"{stem}_transcript.txt"
    output_path.write_text(transcript, encoding="utf-8")
    return output_path

def save_summary(summary: MeetingSummary, filename: str) -> Path:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    stem = Path(filename).stem
    output_path = OUTPUTS_DIR / f"{stem}_summary.md"

    lines = []
    lines.append(f"# Ringkasan Meeting — {stem}\n")
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
            priority_label = {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}.get(item.priority, item.priority)
            lines.append(f"- [{priority_label}]{assignee}: {item.task}")
    else:
        lines.append("## Action Items\n\nTidak ada action items yang terdeteksi.")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path