"""Resume PDF reader — extracts text from local resume files for use in the agent."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pypdf

_PROJ_ROOT = Path(__file__).parent.parent.parent
DEFAULT_RESUME_CN = _PROJ_ROOT / "resume" / "马帮亚_简历_FI-Agent版.pdf"
DEFAULT_RESUME_EN = _PROJ_ROOT / "resume" / "Albert_Ma_Resume.pdf"
DESKTOP_CN = Path.home() / "Desktop" / "马帮亚_简历_FI-Agent版.pdf"
DESKTOP_EN = Path.home() / "Desktop" / "Albert_Ma_Resume.pdf"


def _find_resume(lang: str = "en") -> Optional[Path]:
    """Find the most likely resume PDF path for the given language."""
    if lang == "cn":
        candidates = [DESKTOP_CN, DEFAULT_RESUME_CN]
    else:
        candidates = [DESKTOP_EN, DEFAULT_RESUME_EN]
    for p in candidates:
        if p.exists():
            return p
    return None


def _extract_pdf(path: Path) -> str:
    """Extract plain text from a PDF file."""
    reader = pypdf.PdfReader(str(path))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _clean(text: str) -> str:
    """Remove excessive whitespace while preserving paragraph breaks."""
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def read_resume(lang: str = "en", path: Optional[str] = None) -> str:
    """Read a resume PDF and return cleaned text.

    Args:
        lang: "en" (English) or "cn" (Chinese). Used to pick the default file.
        path: Override the path explicitly.

    Returns:
        Extracted and cleaned text from the PDF.

    Raises:
        FileNotFoundError: No resume PDF found at the given or default path.
    """
    if path:
        p = Path(path)
    else:
        p = _find_resume(lang)

    if not p or not p.exists():
        raise FileNotFoundError(
            f"No resume PDF found. "
            f"Tried: {path or DESKTOP_EN if lang == 'en' else DESKTOP_CN}"
        )

    text = _extract_pdf(p)
    return _clean(text)


def resume_summary(lang: str = "en", path: Optional[str] = None) -> str:
    """Return a compact one-paragraph summary of the resume (first 600 chars)."""
    text = read_resume(lang, path)
    # Strip the very noisy header lines (name + contact info)
    lines = text.splitlines()
    meaningful = [l for l in lines if not re.match(r"^[\u4e00-\u9fff·•|：:]+$", l.strip())]
    content = "\n".join(meaningful)
    return content[:600].rsplit(" ", 1)[0] + "..." if len(content) > 600 else content
