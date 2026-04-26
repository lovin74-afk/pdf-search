from __future__ import annotations

from urllib.parse import quote


def build_pdf_viewer_link(
    file_path: str,
    file_name: str,
    page_number: int,
    query: str,
    x: float,
    y: float,
    font_size: float,
    access_token: str = "",
) -> str | None:
    if not file_path and not file_name:
        return None

    try:
        safe_page_number = max(1, int(page_number))
    except (TypeError, ValueError):
        safe_page_number = 1

    params = [
        "viewer=1",
        f"path={quote(file_path or '')}",
        f"file_name={quote(file_name or '')}",
        f"page={safe_page_number}",
        f"x={x}",
        f"y={y}",
        f"font_size={font_size}",
    ]
    normalized_query = query.strip()
    if normalized_query:
        params.append(f"query={quote(normalized_query)}")
    if access_token:
        params.append(f"access_token={quote(access_token)}")
    return f"?{'&'.join(params)}"
