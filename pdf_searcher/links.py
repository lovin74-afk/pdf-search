from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from pdf_searcher.server import ensure_local_pdf_server


def build_pdf_viewer_link(
    file_path: str,
    page_number: int,
    query: str,
    x: float,
    y: float,
    font_size: float,
    base_url: str | None = None,
) -> str | None:
    path = Path(file_path)
    if not path.is_absolute() or not path.exists():
        return None

    server_base_url = base_url or ensure_local_pdf_server()
    encoded_path = quote(str(path.resolve()))
    params = [
        f"path={encoded_path}",
        f"page={max(1, page_number)}",
        f"x={x}",
        f"y={y}",
        f"font_size={font_size}",
    ]
    normalized_query = query.strip()
    if normalized_query:
        params.append(f"query={quote(normalized_query)}")
    return f"{server_base_url}/viewer?{'&'.join(params)}"
