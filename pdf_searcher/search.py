from __future__ import annotations

import re

SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?|[^\S\r\n]*\n", re.UNICODE)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip().lower()


def _split_sentences(text: str) -> list[dict]:
    sentences: list[dict] = []
    for match in SENTENCE_RE.finditer(text):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        sentences.append(
            {
                "text": sentence,
                "start": match.start(),
                "end": match.end(),
            }
        )
    return sentences


def _find_sentence_window(text: str, start: int, end: int, padding: int = 0) -> tuple[str, str]:
    sentences = _split_sentences(text)
    if not sentences:
        fallback = text[max(0, start - 80) : min(len(text), end + 80)].strip()
        return fallback, fallback

    match_index = 0
    for index, sentence in enumerate(sentences):
        if sentence["end"] > start and sentence["start"] < end:
            match_index = index
            break

    current = sentences[match_index]["text"]
    window_start = max(0, match_index - padding)
    window_end = min(len(sentences), match_index + padding + 1)
    context = " ".join(sentence["text"] for sentence in sentences[window_start:window_end]).strip()
    return current, context


def _match_fragments(fragments: list[dict], start: int, end: int) -> list[dict]:
    matched = []
    for fragment in fragments:
        if fragment["end_char"] <= start:
            continue
        if fragment["start_char"] >= end:
            break
        matched.append(fragment)
    return matched


def search_index(index_data: dict, query: str, limit: int | None = None) -> list[dict]:
    normalized = _normalize_query(query)
    if not normalized:
        return []

    results: list[dict] = []
    for document in index_data["documents"]:
        for page in document["pages"]:
            haystack = page["text"].lower()
            cursor = 0
            match_count = 0
            while True:
                start = haystack.find(normalized, cursor)
                if start == -1:
                    break
                end = start + len(normalized)
                match_count += 1
                matched_fragments = _match_fragments(page["fragments"], start, end)
                anchor = matched_fragments[0] if matched_fragments else {
                    "line_number": 0,
                    "x": 0.0,
                    "y": 0.0,
                    "font_size": 12.0,
                }
                results.append(
                    {
                        "file_name": document["file_name"],
                        "file_path": document["file_path"],
                        "page_number": page["page_number"],
                        "page_label": page["page_label"],
                        "line_number": anchor["line_number"],
                        "x": anchor["x"],
                        "y": anchor["y"],
                        "font_size": anchor.get("font_size", 12.0),
                        "start_char": start,
                        "end_char": end,
                        "match_count": match_count,
                        "snippet": _find_sentence_window(page["text"], start, end, padding=0)[0],
                        "context_snippet": _find_sentence_window(page["text"], start, end, padding=2)[1],
                    }
                )
                cursor = end

    results.sort(key=lambda item: (item["file_name"].lower(), item["page_number"], item["start_char"]))
    if limit is None:
        return results
    return results[:limit]
