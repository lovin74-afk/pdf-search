from __future__ import annotations

import math
import re
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader

WORD_RE = re.compile(r"\w+", re.UNICODE)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _safe_float(value: object) -> float:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return 0.0


def _extract_page_fragments(page) -> list[dict]:
    fragments: list[dict] = []

    def visitor_text(text, cm, tm, font_dict, font_size) -> None:
        cleaned = normalize_text(text)
        if not cleaned:
            return
        x = _safe_float(tm[4] if len(tm) > 4 else 0.0)
        y = _safe_float(tm[5] if len(tm) > 5 else 0.0)
        fragments.append(
            {
                "text": cleaned,
                "x": round(x, 2),
                "y": round(y, 2),
                "font_size": round(_safe_float(font_size), 2),
            }
        )

    try:
        page.extract_text(visitor_text=visitor_text)
    except TypeError:
        text = page.extract_text() or ""
        if normalize_text(text):
            fragments.append({"text": normalize_text(text), "x": 0.0, "y": 0.0, "font_size": 0.0})

    fragments.sort(key=lambda item: (-item["y"], item["x"], item["text"]))
    return fragments


def _annotate_fragments(fragments: list[dict]) -> tuple[str, list[dict]]:
    line_lookup: dict[int, int] = {}
    line_counter = 0
    buffer: list[str] = []
    cursor = 0

    for fragment in fragments:
        line_key = int(round(fragment["y"] / 14.0)) if fragment["y"] else 0
        if line_key not in line_lookup:
            line_counter += 1
            line_lookup[line_key] = line_counter

        if buffer:
            buffer.append(" ")
            cursor += 1

        start = cursor
        text = fragment["text"]
        buffer.append(text)
        cursor += len(text)
        fragment["start_char"] = start
        fragment["end_char"] = cursor
        fragment["line_number"] = line_lookup[line_key]

    page_text = "".join(buffer)
    return page_text, fragments


def _read_pdf(source: BinaryIO | BytesIO | str | Path) -> PdfReader:
    return PdfReader(source)


def _index_reader(reader: PdfReader, file_name: str, file_path: str) -> dict:
    pages: list[dict] = []
    fragment_count = 0

    for page_number, page in enumerate(reader.pages, start=1):
        fragments = _extract_page_fragments(page)
        page_text, fragments = _annotate_fragments(fragments)
        fragment_count += len(fragments)
        pages.append(
            {
                "page_number": page_number,
                "page_label": f"{page_number}페이지",
                "text": page_text,
                "fragments": fragments,
            }
        )

    return {
        "file_name": file_name,
        "file_path": file_path,
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "fragment_count": fragment_count,
        },
    }


def build_index_from_folder(folder: Path) -> dict:
    pdf_files = sorted(path for path in folder.rglob("*.pdf") if path.is_file())
    documents = [_index_reader(_read_pdf(path), path.name, str(path.resolve())) for path in pdf_files]
    return _finalize_index(documents, source=str(folder.resolve()))


def build_index_from_uploaded_files(files) -> dict:
    documents = []
    for file in files:
        content = file.read()
        reader = _read_pdf(BytesIO(content))
        documents.append(_index_reader(reader, file.name, file.name))
    return _finalize_index(documents, source="uploaded")


def _finalize_index(documents: list[dict], source: str) -> dict:
    page_count = sum(doc["summary"]["page_count"] for doc in documents)
    fragment_count = sum(doc["summary"]["fragment_count"] for doc in documents)
    word_freq: defaultdict[str, int] = defaultdict(int)

    for doc in documents:
        for page in doc["pages"]:
            for word in WORD_RE.findall(page["text"].lower()):
                word_freq[word] += 1

    return {
        "source": source,
        "documents": documents,
        "summary": {
            "file_count": len(documents),
            "page_count": page_count,
            "fragment_count": fragment_count,
            "unique_terms": len(word_freq),
        },
        "terms": dict(sorted(word_freq.items(), key=lambda item: (-item[1], item[0]))),
    }
