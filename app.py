from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import quote

import streamlit as st

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None
    filedialog = None

from pdf_searcher.db import (
    get_latest_saved_index,
    get_saved_indexes,
    load_index_from_db,
    save_index_to_db,
)
from pdf_searcher.indexer import (
    build_index_from_folder,
    build_index_from_uploaded_files,
)
from pdf_searcher.links import build_pdf_viewer_link
from pdf_searcher.server import ensure_local_pdf_server
from pdf_searcher.settings import load_settings, update_settings
from pdf_searcher.search import search_index


DB_FILE = Path(".pdf_search_index") / "indexes.db"
SETTINGS_FILE = Path(".pdf_search_index") / "settings.json"


def highlight_query(text: str, query: str) -> str:
    escaped_text = html.escape(text)
    escaped_query = html.escape(query.strip())
    if not escaped_query:
        return escaped_text

    pattern = re.compile(re.escape(escaped_query), re.IGNORECASE)
    return pattern.sub(lambda match: f"<mark>{match.group(0)}</mark>", escaped_text)


def normalize_recent_searches(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized[:5]


def ensure_state() -> None:
    if "index_data" not in st.session_state:
        st.session_state.index_data = None
    if "index_source" not in st.session_state:
        st.session_state.index_source = ""
    if "folder_input" not in st.session_state:
        st.session_state.folder_input = ""
    if "folder_input_pending" not in st.session_state:
        st.session_state.folder_input_pending = ""
    if "autoload_attempted" not in st.session_state:
        st.session_state.autoload_attempted = False
    if "search_input" not in st.session_state:
        st.session_state.search_input = ""
    if "search_input_pending" not in st.session_state:
        st.session_state.search_input_pending = ""
    if "recent_searches" not in st.session_state:
        st.session_state.recent_searches = []

    if st.session_state.folder_input_pending:
        st.session_state.folder_input = st.session_state.folder_input_pending
        st.session_state.folder_input_pending = ""

    if st.session_state.search_input_pending:
        st.session_state.search_input = st.session_state.search_input_pending
        st.session_state.search_input_pending = ""

    settings = load_settings(SETTINGS_FILE)
    if not st.session_state.folder_input:
        last_folder = settings.get("last_folder", "")
        if isinstance(last_folder, str):
            st.session_state.folder_input = last_folder
    if not st.session_state.recent_searches:
        recent_searches = settings.get("recent_searches", [])
        if isinstance(recent_searches, list):
            st.session_state.recent_searches = normalize_recent_searches(
                [item for item in recent_searches if isinstance(item, str)]
            )

    if not st.session_state.autoload_attempted and st.session_state.index_data is None:
        latest = get_latest_saved_index(DB_FILE)
        if latest:
            st.session_state.index_data = load_index_from_db(DB_FILE, latest["id"])
            st.session_state.index_source = (
                f"#{latest['id']} | {latest['label']} | {latest['created_at']}"
            )
        st.session_state.autoload_attempted = True


def choose_folder() -> str:
    if tk is None or filedialog is None:
        return ""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory()
    finally:
        root.destroy()
    return selected or ""


def render_result_card(result: dict, query: str) -> None:
    viewer_link = build_pdf_viewer_link(
        result["file_path"],
        result["page_number"],
        query,
        result["x"],
        result["y"],
        result["font_size"],
    )
    if viewer_link:
        title = (
            f'<a href="{html.escape(viewer_link)}" target="_blank" rel="noopener noreferrer">'
            f'{html.escape(result["file_name"])} | {html.escape(result["page_label"])}</a>'
        )
        st.markdown(f"### {title}", unsafe_allow_html=True)
    else:
        st.markdown(f"### {result['file_name']} | {result['page_label']}")
    st.write(
        f"위치: 줄 {result['line_number']} | x={result['x']:.1f}, y={result['y']:.1f} | "
        f"일치 {result['match_count']}회"
    )
    st.markdown(
        f"""
        <div style="white-space: normal; overflow-wrap: anywhere; line-height: 1.7;
                    padding: 0.9rem 1rem; border: 1px solid #d9d9d9; border-radius: 0.6rem;
                    background: #fafafa; margin-bottom: 0.5rem;">
            {highlight_query(result["snippet"], query)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("상세 정보"):
        st.write(f"파일 경로: {result['file_path']}")
        st.write(f"검색어: {query}")
        st.write(f"문자 위치: {result['start_char']} - {result['end_char']}")
        if viewer_link:
            st.markdown(
                f'[새 탭에서 이 위치 열기]({viewer_link})'
            )
        else:
            st.caption("이 결과는 로컬 파일 경로가 없어 바로 열기 링크를 만들 수 없습니다.")
        st.write("확장 문맥")
        st.markdown(
            f"""
            <div style="white-space: normal; overflow-wrap: anywhere; line-height: 1.7;
                        padding: 0.9rem 1rem; border: 1px solid #d9d9d9; border-radius: 0.6rem;
                        background: #fafafa;">
                {highlight_query(result["context_snippet"], query)}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    with st.sidebar:
        st.header("색인 만들기")
        folder = st.text_input(
            "PDF 폴더 경로",
            key="folder_input",
            placeholder=r"C:\Users\user\Documents\pdfs",
            help="하위 폴더까지 재귀적으로 스캔합니다.",
        )
        if tk is not None and filedialog is not None:
            if st.button("폴더 선택", use_container_width=True):
                selected = choose_folder()
                if selected:
                    st.session_state.folder_input_pending = selected
                    update_settings(SETTINGS_FILE, {"last_folder": selected})
                    st.rerun()
        else:
            st.caption("이 배포 환경에서는 폴더 선택 창을 지원하지 않아 경로를 직접 입력해야 합니다.")
        if st.button("폴더 색인 생성", use_container_width=True):
            if not folder.strip():
                st.error("PDF 폴더 경로를 입력해 주세요.")
            else:
                folder_path = Path(folder).expanduser()
                if not folder_path.exists():
                    st.error("입력한 폴더를 찾을 수 없습니다.")
                else:
                    update_settings(SETTINGS_FILE, {"last_folder": str(folder_path.resolve())})
                    with st.spinner("PDF를 읽고 색인을 만드는 중입니다..."):
                        index_data = build_index_from_folder(folder_path)
                        record_id = save_index_to_db(index_data, DB_FILE, label=str(folder_path.resolve()))
                        st.session_state.index_data = index_data
                        st.session_state.index_source = f"{folder_path} (DB #{record_id})"
                    st.success(
                        f"{index_data['summary']['file_count']}개 PDF, "
                        f"{index_data['summary']['page_count']}개 페이지를 색인했고 DB에 저장했습니다."
                    )

        uploads = st.file_uploader(
            "또는 PDF 파일 업로드",
            type=["pdf"],
            accept_multiple_files=True,
        )
        if st.button("업로드 파일 색인 생성", use_container_width=True):
            if not uploads:
                st.error("하나 이상의 PDF 파일을 업로드해 주세요.")
            else:
                with st.spinner("업로드한 PDF를 읽는 중입니다..."):
                    index_data = build_index_from_uploaded_files(uploads)
                    record_id = save_index_to_db(index_data, DB_FILE, label="uploaded files")
                    st.session_state.index_data = index_data
                    st.session_state.index_source = f"uploaded files (DB #{record_id})"
                st.success(
                    f"{index_data['summary']['file_count']}개 PDF를 색인했고 DB에 저장했습니다."
                )

        saved_indexes = get_saved_indexes(DB_FILE)
        if saved_indexes:
            options = {
                f"#{item['id']} | {item['label']} | {item['created_at']}": item["id"]
                for item in saved_indexes
            }
            selected_label = st.selectbox("저장된 색인", list(options.keys()), index=0)
            if st.button("선택한 색인 불러오기", use_container_width=True):
                record_id = options[selected_label]
                st.session_state.index_data = load_index_from_db(DB_FILE, record_id)
                st.session_state.index_source = selected_label
                st.success("DB에서 저장된 색인을 불러왔습니다.")
        else:
            st.caption("아직 저장된 색인이 없습니다.")


def save_recent_search(query: str) -> None:
    cleaned = query.strip()
    if not cleaned:
        return
    recent = [cleaned, *st.session_state.recent_searches]
    st.session_state.recent_searches = normalize_recent_searches(recent)
    update_settings(SETTINGS_FILE, {"recent_searches": st.session_state.recent_searches})


def on_search_input_change() -> None:
    save_recent_search(st.session_state.search_input)


def delete_recent_search(query: str) -> None:
    st.session_state.recent_searches = [item for item in st.session_state.recent_searches if item != query]
    update_settings(SETTINGS_FILE, {"recent_searches": st.session_state.recent_searches})


def process_recent_search_action() -> None:
    action = st.query_params.get("recent_action")
    value = st.query_params.get("recent_value")
    if not action or not value:
        return

    if action == "search":
        cleaned = value.strip()
        if cleaned:
            st.session_state.search_input = cleaned
            st.session_state.search_input_pending = ""
            save_recent_search(cleaned)
    elif action == "delete":
        delete_recent_search(value)

    st.query_params.clear()
    st.rerun()


def render_recent_searches() -> None:
    recent_searches = st.session_state.recent_searches
    if not recent_searches:
        return

    chips: list[str] = []
    for term in recent_searches:
        encoded = quote(term)
        chips.append(
            f'<span class="recent-chip">'
            f'<form class="recent-chip-form" method="get">'
            f'<input type="hidden" name="recent_action" value="search">'
            f'<input type="hidden" name="recent_value" value="{html.escape(term)}">'
            f'<button type="submit" class="recent-chip-term">{html.escape(term)}</button>'
            f"</form>"
            f'<form class="recent-chip-form" method="get">'
            f'<input type="hidden" name="recent_action" value="delete">'
            f'<input type="hidden" name="recent_value" value="{html.escape(term)}">'
            f'<button type="submit" class="recent-chip-delete" aria-label="{html.escape(term)} 삭제">x</button>'
            f"</form>"
            f"</span>"
        )

    st.markdown(
        f"""
        <style>
        .recent-searches {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
            margin-top: -0.15rem;
            margin-bottom: 0.5rem;
        }}
        .recent-chip {{
            display: inline-flex;
            align-items: center;
            border: 1px solid #d1d5db;
            border-radius: 999px;
            background: #f8fafc;
            overflow: hidden;
            width: fit-content;
        }}
        .recent-chip-form {{
            margin: 0;
        }}
        .recent-chip button {{
            border: 0;
            background: transparent;
            color: #111827;
            font-size: 0.76rem;
            line-height: 1;
            cursor: pointer;
        }}
        .recent-chip-term {{
            padding: 0.24rem 0.42rem 0.24rem 0.5rem;
        }}
        .recent-chip-delete {{
            padding: 0.24rem 0.38rem 0.24rem 0.18rem;
            border-left: 1px solid #e5e7eb;
            color: #6b7280;
        }}
        .recent-chip-term:hover, .recent-chip-delete:hover {{
            background: #eef2f7;
        }}
        </style>
        <div class="recent-searches">{''.join(chips)}</div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="PDF Searcher", page_icon="PDF", layout="wide")
    ensure_state()
    process_recent_search_action()
    ensure_local_pdf_server()
    render_sidebar()

    st.title("PDF Searcher")
    st.caption("여러 PDF를 색인하고, 단어를 검색해 파일과 위치를 찾습니다.")

    index_data = st.session_state.index_data
    if not index_data:
        st.info("왼쪽에서 PDF 폴더를 색인하거나 파일을 업로드해 시작해 주세요.")
        return

    summary = index_data["summary"]
    col1, col2, col3 = st.columns(3)
    col1.metric("PDF 파일", summary["file_count"])
    col2.metric("페이지", summary["page_count"])
    col3.metric("텍스트 조각", summary["fragment_count"])
    st.caption(f"현재 색인 소스: {st.session_state.index_source}")

    query = st.text_input(
        "검색어",
        key="search_input",
        placeholder="예: 계약, invoice, machine learning",
        on_change=on_search_input_change,
    )
    render_recent_searches()

    if query.strip():
        results = search_index(index_data, query, limit=None)
        st.subheader(f"검색 결과 {len(results)}건")
        if not results:
            st.warning("일치하는 결과를 찾지 못했습니다.")
        else:
            for result in results:
                render_result_card(result, query)
    else:
        st.write("검색어를 입력하면 결과가 여기에 표시됩니다.")


if __name__ == "__main__":
    main()
