"""
llm-wiki-ingest — Standalone MCP Server

Receives various input formats and returns clean markdown.
Does not know about wiki, does not call wiki tools, does not import from llm-wiki.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(os.environ.get("ASSETS_DIR", "/assets"))
INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/input"))

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("llm-wiki-ingest")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MIN_IMAGE_BYTES = 5 * 1024  # 5 KB


def _slug(text: str, max_len: int = 30) -> str:
    """Convert arbitrary text to a lowercase kebab-case slug."""
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:max_len].rstrip("-")


def _today() -> str:
    return date.today().isoformat()


def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ---------------------------------------------------------------------------
# Tool 1: ingest_image
# ---------------------------------------------------------------------------


@mcp.tool()
def ingest_image(path: str, caption: str = "") -> str:
    """Copy an image from /input to /assets and return an Obsidian embed string.

    Args:
        path: Absolute path to the image file (e.g. /input/chart.png).
        caption: Optional figure caption.

    Returns:
        Obsidian ![[assets/...]] embed string, optionally followed by a caption.
    """
    src = Path(path)
    if not src.exists():
        return f"✗ File not found: {path}"

    try:
        size = src.stat().st_size
    except OSError as exc:
        return f"✗ Cannot read file: {exc}"

    if size < _MIN_IMAGE_BYTES:
        return f"✗ Image too small ({size} bytes < 5 KB), skipped."

    slug_part = _slug(src.stem) or "image"
    dest_name = f"{_now_ts()}-{slug_part}{src.suffix.lower()}"
    dest = ASSETS_DIR / dest_name

    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        return f"✗ Failed to copy image: {exc}"

    embed = f"![[assets/{dest_name}]]"
    if caption:
        embed += f"\n*Figure: {caption}*"
    return embed


# ---------------------------------------------------------------------------
# Tool 2: ingest_clipboard
# ---------------------------------------------------------------------------


@mcp.tool()
def ingest_clipboard(content: str, source_url: str = "") -> str:
    """Convert HTML or plain text clipboard content to clean markdown.

    Args:
        content: HTML or plain text string to convert.
        source_url: Optional source URL for attribution.

    Returns:
        Clean markdown string.
    """
    import html2text
    from bs4 import BeautifulSoup

    is_html = bool(re.search(r"<[a-zA-Z][^>]*>", content))

    if is_html:
        soup = BeautifulSoup(content, "lxml")

        # Remove noise elements
        _REMOVE_SELECTORS = [
            "nav", "header", "footer", "aside",
            ".sidebar", ".ad", "script", "style", "iframe",
        ]
        _REMOVE_ATTR_PATTERNS = ["cookie", "popup", "newsletter"]

        for sel in _REMOVE_SELECTORS:
            for tag in soup.select(sel):
                tag.decompose()

        for tag in soup.find_all(True):
            classes = " ".join(tag.get("class", []))
            if any(p in classes for p in _REMOVE_ATTR_PATTERNS):
                tag.decompose()

        # Extract title and remove h1 from body to avoid duplication
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
            h1.decompose()
        elif soup.title:
            title = soup.title.get_text(strip=True)

        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.body_width = 0
        converter.unicode_snob = True

        body = converter.handle(str(soup))
    else:
        # Plain text: normalize whitespace only
        body = re.sub(r"\r\n|\r", "\n", content)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        title = ""

    lines: list[str] = []

    if source_url:
        lines.append(f"> Source: {source_url} (clipped {_today()})")
        lines.append("")

    if title:
        lines.append(f"# {title}")
        lines.append("")

    lines.append(body.strip())

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: ingest_excel
# ---------------------------------------------------------------------------


@mcp.tool()
def ingest_excel(path: str, sheet_name: str = "") -> str:
    """Convert an Excel file to markdown tables.

    Args:
        path: Absolute path to the .xlsx file (e.g. /input/backtest.xlsx).
        sheet_name: Optional sheet name; if empty, all sheets are included.

    Returns:
        Markdown string with one section per sheet.
    """
    import pandas as pd

    src = Path(path)
    if not src.exists():
        return f"✗ File not found: {path}"

    try:
        xl = pd.ExcelFile(src, engine="openpyxl")
    except Exception as exc:
        return f"✗ Failed to open Excel file: {exc}"

    sheets = [sheet_name] if sheet_name else xl.sheet_names

    lines: list[str] = [f"# {src.name}", ""]

    for sname in sheets:
        lines.append(f"## Sheet: {sname}")

        try:
            df = xl.parse(sname)
        except Exception as exc:
            lines.append(f"*(error reading sheet: {exc})*")
            lines.append("")
            continue

        if df.empty:
            lines.append("*(empty)*")
            lines.append("")
            continue

        # Detect datetime columns
        has_dt = any(
            pd.api.types.is_datetime64_any_dtype(df[c]) for c in df.columns
        )
        if has_dt:
            lines.append("*Time series data detected*")
            lines.append("")

        total_rows = len(df)

        # Truncate large frames
        if total_rows > 50:
            display_df = pd.concat([df.head(10), df.tail(5)])
            note = f"*{total_rows} rows total — showing first 10 and last 5*"
        else:
            display_df = df
            note = ""

        # Format floats to 4 significant figures
        def _fmt(x):
            if isinstance(x, float):
                return f"{x:.4g}"
            return x

        display_df = display_df.apply(lambda col: col.map(_fmt))

        try:
            md_table = display_df.to_markdown(index=False)
        except Exception:
            md_table = display_df.to_string(index=False)

        lines.append(md_table)
        if note:
            lines.append(note)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4: ingest_note
# ---------------------------------------------------------------------------


@mcp.tool()
def ingest_note(raw_text: str, hint: str = "") -> str:
    """Structure raw unstructured text into markdown with frontmatter suggestions.

    Uses local NLP only (spacy + sumy). No external API calls.

    Args:
        raw_text: Raw unstructured text to process.
        hint: Optional hint string for type detection and slug suggestion.

    Returns:
        Structured markdown with YAML frontmatter comments.
    """
    hint_lower = hint.lower()

    # Rule-based type detection
    if any(kw in hint_lower for kw in ("strategy", "trading", "backtest")):
        note_type = "strategy"
        prefix = "strategy-"
    elif any(kw in hint_lower for kw in ("concept", "theory", "definition")):
        note_type = "concept"
        prefix = "concept-"
    elif any(kw in hint_lower for kw in ("book", "paper", "chapter")):
        note_type = "source"
        prefix = "source-"
    else:
        note_type = "log"
        prefix = "log-"

    hint_slug = _slug(hint, 25) if hint else _today()
    suggested_slug = f"{prefix}{hint_slug}"[:30].rstrip("-")

    hint_title = hint.strip().title() if hint else "Note"
    suggested_title = hint_title
    suggested_tags = note_type

    # Try spacy + sumy
    try:
        import spacy
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.summarizers.lsa import LsaSummarizer

        nlp = spacy.load("en_core_web_sm")
        doc = nlp(raw_text)

        # Named entities
        entities: list[str] = []
        seen_ents: set[str] = set()
        for ent in doc.ents:
            key = (ent.text.strip(), ent.label_)
            if key not in seen_ents:
                entities.append(f"`{ent.text.strip()}` ({ent.label_})")
                seen_ents.add(key)

        # Top 5 noun chunks by frequency
        chunk_freq: dict[str, int] = {}
        for chunk in doc.noun_chunks:
            t = chunk.text.strip().lower()
            if t:
                chunk_freq[t] = chunk_freq.get(t, 0) + 1
        top_chunks = sorted(chunk_freq, key=chunk_freq.__getitem__, reverse=True)[:5]

        # Update tags from top chunks
        tag_list = [note_type] + [_slug(c, 20) for c in top_chunks[:3] if c]
        suggested_tags = ", ".join(dict.fromkeys(tag_list))

        # sumy summary
        try:
            parser = PlaintextParser.from_string(raw_text, Tokenizer("english"))
            summarizer = LsaSummarizer()
            summary_sentences = [str(s) for s in summarizer(parser.document, 3)]
            summary = " ".join(summary_sentences)
        except Exception:
            # Fallback: first 2 sentences
            sentences = re.split(r"(?<=[.!?])\s+", raw_text.strip())
            summary = " ".join(sentences[:2])

        spacy_ok = True
    except Exception:
        spacy_ok = False
        entities = []
        summary = ""

    if not spacy_ok:
        # Full fallback when spacy is unavailable
        date_slug = _today().replace("-", "")
        hint_part = _slug(hint, 15) if hint else "note"
        fallback_slug = f"log-{date_slug}-{hint_part}"[:30].rstrip("-")
        lines = [
            f"<!-- suggested-slug: {fallback_slug} -->",
            f"<!-- suggested-title: Note: {hint} -->",
            "<!-- suggested-tags: log -->",
            "",
            "## Content",
            raw_text,
        ]
        return "\n".join(lines)

    # Extract existing bullet points from raw text
    bullet_lines = [
        ln.strip()
        for ln in raw_text.splitlines()
        if re.match(r"^[-*•]\s+", ln.strip())
    ]

    lines: list[str] = [
        f"<!-- suggested-slug: {suggested_slug} -->",
        f"<!-- suggested-title: {suggested_title} -->",
        f"<!-- suggested-tags: {suggested_tags} -->",
        "",
        "## Summary",
        summary,
        "",
        "## Key Points",
    ]

    if bullet_lines:
        lines.extend(bullet_lines)
    else:
        lines.append("*(no bullet points found in raw text)*")

    lines += [
        "",
        "## Entities Detected",
        ", ".join(entities) if entities else "*(none detected)*",
        "",
        "## Raw Content",
        raw_text,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 5: ingest_pdf
# ---------------------------------------------------------------------------


@mcp.tool()
def ingest_pdf(path: str, use_marker: bool = False) -> str:
    """Convert a PDF file to clean markdown.

    Args:
        path: Absolute path to the PDF file (e.g. /input/paper.pdf).
        use_marker: If True, use Marker (slower, higher quality). Falls back to
                    pymupdf4llm on failure.

    Returns:
        Markdown string with inline Obsidian image embeds.
    """
    src = Path(path)
    if not src.exists():
        return f"✗ File not found: {path}"

    stem = _slug(src.stem) or "document"
    markdown_content = ""

    if use_marker:
        try:
            markdown_content = _convert_with_marker(src)
        except Exception:
            markdown_content = ""  # silent fallback

    if not markdown_content:
        try:
            markdown_content = _convert_with_pymupdf(src)
        except Exception as exc:
            return f"✗ PDF conversion failed: {exc}"

    # Extract images
    image_refs = _extract_pdf_images(src, stem)

    # Detect title: first non-empty line that looks like a heading
    title = src.stem
    for ln in markdown_content.splitlines():
        ln = ln.strip()
        if ln.startswith("#"):
            title = ln.lstrip("#").strip()
            break
        elif ln:
            title = ln
            break

    lines: list[str] = [
        f"# {title}",
        "",
        markdown_content.strip(),
    ]

    if image_refs:
        lines += ["", "## Extracted Figures", ""]
        lines.extend(image_refs)

    return "\n".join(lines)


def _convert_with_pymupdf(src: Path) -> str:
    import pymupdf4llm

    return pymupdf4llm.to_markdown(str(src))


def _convert_with_marker(src: Path) -> str:
    import os as _os

    _os.environ.setdefault("TORCH_DEVICE", "cpu")

    from marker.convert import convert_single_pdf
    from marker.models import load_all_models

    models = load_all_models()
    full_text, _images, _metadata = convert_single_pdf(str(src), models)
    return full_text


def _extract_pdf_images(src: Path, stem: str) -> list[str]:
    """Extract images from PDF, save to ASSETS_DIR, return Obsidian embed strings."""
    import fitz  # PyMuPDF

    refs: list[str] = []
    try:
        doc = fitz.open(str(src))
    except Exception:
        return refs

    page_img_counters: dict[int, int] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            img_bytes = base_image["image"]
            if len(img_bytes) < _MIN_IMAGE_BYTES:
                continue

            ext = base_image.get("ext", "png")
            counter = page_img_counters.get(page_num, 0) + 1
            page_img_counters[page_num] = counter

            filename = f"{stem}-p{page_num + 1}-img{counter}.{ext}"
            dest = ASSETS_DIR / filename
            try:
                dest.write_bytes(img_bytes)
            except OSError:
                continue

            refs.append(f"![[assets/{filename}]]")

    doc.close()
    return refs


# ---------------------------------------------------------------------------
# Tool 6: ingest_pdf_url
# ---------------------------------------------------------------------------


@mcp.tool()
def ingest_pdf_url(url: str) -> str:
    """Download and convert a PDF (or arXiv HTML) from a URL to clean markdown.

    Args:
        url: URL to a PDF or arXiv paper (e.g. https://arxiv.org/pdf/2401.12345).

    Returns:
        Markdown string.
    """
    import httpx

    # arXiv detection
    arxiv_pdf_pattern = re.compile(
        r"https?://arxiv\.org/pdf/(\d{4}\.\d+)(v\d+)?(\.pdf)?", re.I
    )
    m = arxiv_pdf_pattern.match(url)

    if m:
        paper_id = m.group(1)
        html_url = f"https://arxiv.org/html/{paper_id}"
        try:
            resp = httpx.get(html_url, timeout=60, follow_redirects=True)
            if resp.status_code == 200 and "text/html" in resp.headers.get(
                "content-type", ""
            ):
                return ingest_clipboard(resp.text, source_url=html_url)
        except Exception:
            pass  # fall through to PDF download

    # Generic PDF download
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        with httpx.stream("GET", url, timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with tmp_path.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)

        result = ingest_pdf(str(tmp_path))
        return result
    except Exception as exc:
        return f"✗ Failed to download or convert URL: {exc}"
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
