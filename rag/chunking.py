"""Stages 1 and 2 of the RAG pipeline: Load and Chunk.

Documents are Markdown files under rag/knowledge/. Each "## " section becomes one chunk. A section that is longer
than MAX_CHARS is split into overlapping windows of whole lines. All character ranges refer to the document text
after line endings were normalised to LF.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path("rag") / "knowledge"
MAX_CHARS = 700
OVERLAP = 100

_VERSION_RE = re.compile(r"^Version:\s*(v\d+)", re.MULTILINE)
_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Document:
    source: str  # file name, for example payment_test_policy.md
    version: str  # for example v1
    title: str
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # for example payment_test_policy.md#failure-handling-pt-4-to-pt-6
    source: str
    version: str
    section: str
    start: int  # character range in Document.text
    end: int
    text: str  # what is embedded and shown to the model


@dataclass(frozen=True)
class _Line:
    start: int
    end: int
    text: str


def load_documents(directory: Path = KNOWLEDGE_DIR) -> list[Document]:
    documents = []
    for path in sorted(Path(directory).glob("*.md")):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
        version_match = _VERSION_RE.search(text)
        documents.append(
            Document(
                source=path.name,
                version=version_match.group(1) if version_match else "unversioned",
                title=title_match.group(1).strip() if title_match else path.stem,
                text=text,
            )
        )
    return documents


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _sections(doc: Document) -> list[tuple[str, int, int]]:
    """Return (section name, start, end) for the overview and every '## ' section."""
    headings = list(_HEADING_RE.finditer(doc.text))
    first = headings[0].start() if headings else len(doc.text)
    result = []
    if doc.text[:first].strip():
        result.append(("Overview", 0, first))
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(doc.text)
        result.append((match.group(1).strip(), match.start(), end))
    return result


def _lines(doc: Document, start: int, end: int) -> list[_Line]:
    lines, pos = [], start
    for raw in doc.text[start:end].split("\n"):
        lines.append(_Line(pos, pos + len(raw), raw))
        pos += len(raw) + 1
    return lines


def _windows(lines: list[_Line], max_chars: int, overlap: int) -> list[tuple[int, int]]:
    """Group line indexes into windows of at most max_chars (one line may exceed it); neighbours overlap."""
    windows, i = [], 0
    while i < len(lines):
        j, size = i, 0
        while j < len(lines) and (j == i or size + len(lines[j].text) + 1 <= max_chars):
            size += len(lines[j].text) + 1
            j += 1
        windows.append((i, j))
        if j >= len(lines):
            break
        k, back = j, 0
        while k - 1 > i and back + len(lines[k - 1].text) + 1 <= overlap:
            k -= 1
            back += len(lines[k].text) + 1
        i = k  # k > i, so every pass makes progress
    return windows


def chunk_document(doc: Document, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[Chunk]:
    chunks = []
    for section, start, end in _sections(doc):
        lines = _lines(doc, start, end)
        windows = _windows(lines, max_chars, overlap)
        for number, (a, b) in enumerate(windows, start=1):
            body_start, body_end = lines[a].start, lines[b - 1].end
            body = doc.text[body_start:body_end].strip()
            if not body:
                continue
            suffix = f"-{number}" if len(windows) > 1 else ""
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.source}#{_slug(section)}{suffix}",
                    source=doc.source,
                    version=doc.version,
                    section=section,
                    start=body_start,
                    end=body_end,
                    text=f"{doc.title} | {section}\n{body}",
                )
            )
    return chunks


def load_chunks(directory: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    return [chunk for doc in load_documents(directory) for chunk in chunk_document(doc)]
