from pathlib import Path

PROMPTS_DIR = Path("prompts")

def load_prompt(filename: str, **kwargs) -> str:
    path = PROMPTS_DIR / filename
    template = path.read_text(encoding="utf-8")
    return template.format(**kwargs)