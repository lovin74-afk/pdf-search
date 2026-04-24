from pathlib import Path

from pdf_searcher.links import build_pdf_viewer_link
from pdf_searcher.server import _build_content_disposition, _parse_range_header


def test_build_pdf_viewer_link_for_local_pdf() -> None:
    pdf_path = Path("sample file.pdf")
    pdf_path.write_text("dummy", encoding="utf-8")
    try:
        link = build_pdf_viewer_link(
            str(pdf_path.resolve()),
            pdf_path.name,
            3,
            "beta gamma",
            120.5,
            640.0,
            11.0,
        )
        assert link is not None
        assert "viewer=1" in link
        assert "file_name=sample%20file.pdf" in link
        assert "page=3" in link
        assert "query=beta%20gamma" in link
        assert "x=120.5" in link
        assert "font_size=11.0" in link
        assert link.startswith("?viewer=1&path=")
    finally:
        if pdf_path.exists():
            pdf_path.unlink()


def test_build_pdf_viewer_link_returns_none_for_non_local_entry() -> None:
    assert build_pdf_viewer_link("", "", 1, "beta", 0.0, 0.0, 12.0) is None


def test_parse_range_header_supports_standard_byte_ranges() -> None:
    assert _parse_range_header("bytes=100-199", 1000) == (100, 199)
    assert _parse_range_header("bytes=100-", 1000) == (100, 999)
    assert _parse_range_header("bytes=-200", 1000) == (800, 999)


def test_build_content_disposition_supports_unicode_filename() -> None:
    header = _build_content_disposition("여비지급 규칙.pdf")
    assert 'filename="' in header
    assert "filename*=UTF-8''" in header
