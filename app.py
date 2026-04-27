from __future__ import annotations

import base64
import hmac
import json
import os

import html
import re
import time
from pathlib import Path
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

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
from pdf_searcher.settings import load_settings, update_settings
from pdf_searcher.search import search_index


DB_FILE = Path(".pdf_search_index") / "indexes.db"
SETTINGS_FILE = Path(".pdf_search_index") / "settings.json"
UPLOADED_ORIGINALS_DIR = Path(".uploaded_originals")


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


def get_auth_credentials() -> tuple[str, str]:
    secret_username = st.secrets.get("APP_USERNAME", "")
    secret_password = st.secrets.get("APP_PASSWORD", "")
    env_username = os.getenv("APP_USERNAME", "")
    env_password = os.getenv("APP_PASSWORD", "")

    username = str(secret_username or env_username).strip()
    password = str(secret_password or env_password)
    return username, password


def get_auth_settings() -> tuple[int, int]:
    secret_attempts = st.secrets.get("APP_MAX_LOGIN_ATTEMPTS", 5)
    secret_lockout = st.secrets.get("APP_LOCKOUT_MINUTES", 15)
    env_attempts = os.getenv("APP_MAX_LOGIN_ATTEMPTS")
    env_lockout = os.getenv("APP_LOCKOUT_MINUTES")

    try:
        max_attempts = max(1, int(env_attempts if env_attempts is not None else secret_attempts))
    except (TypeError, ValueError):
        max_attempts = 5

    try:
        lockout_minutes = max(1, int(env_lockout if env_lockout is not None else secret_lockout))
    except (TypeError, ValueError):
        lockout_minutes = 15

    return max_attempts, lockout_minutes


def check_credentials(username: str, password: str) -> bool:
    expected_username, expected_password = get_auth_credentials()
    if not expected_username or not expected_password:
        return False
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


def build_app_access_token() -> str:
    expected_username, expected_password = get_auth_credentials()
    if not expected_username or not expected_password:
        return ""
    message = f"{expected_username}|app-access".encode("utf-8")
    return hmac.new(expected_password.encode("utf-8"), message, "sha256").hexdigest()


def is_valid_app_access_token(access_token: str) -> bool:
    if not access_token:
        return False
    expected_token = build_app_access_token()
    if not expected_token:
        return False
    return hmac.compare_digest(access_token, expected_token)


def build_viewer_access_token(file_path: str, file_name: str, page_number: int, query: str) -> str:
    _, expected_password = get_auth_credentials()
    message = f"{file_path}|{file_name}|{page_number}|{query.strip()}".encode("utf-8")
    return hmac.new(expected_password.encode("utf-8"), message, "sha256").hexdigest()


def is_valid_viewer_access_token(file_path: str, file_name: str, page_number: int, query: str, access_token: str) -> bool:
    expected_username, expected_password = get_auth_credentials()
    if not expected_username or not expected_password or not access_token:
        return False
    expected_token = build_viewer_access_token(file_path, file_name, page_number, query)
    return hmac.compare_digest(access_token, expected_token)


RESULT_BOX_STYLE = """
<style>
.result-snippet-box {
    white-space: normal;
    overflow-wrap: anywhere;
    line-height: 1.7;
    padding: 0.9rem 1rem;
    border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
    border-radius: 0.6rem;
    background: color-mix(in srgb, var(--background-color) 88%, var(--text-color) 4%);
    color: var(--text-color);
    margin-bottom: 0.5rem;
}
.result-snippet-box mark {
    background: color-mix(in srgb, #facc15 72%, transparent);
    color: inherit;
    padding: 0 0.1rem;
    border-radius: 0.2rem;
}
@supports not (background: color-mix(in srgb, white 50%, black 50%)) {
    .result-snippet-box {
        border: 1px solid rgba(128, 128, 128, 0.35);
        background: rgba(127, 127, 127, 0.08);
        color: inherit;
    }
    .result-snippet-box mark {
        background: rgba(250, 204, 21, 0.55);
        color: inherit;
    }
}
</style>
"""


VIEWER_HTML_TEMPLATE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PDF Viewer</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f3efe6;
      --surface: rgba(255,255,255,0.94);
      --text: #17202a;
      --muted: #51606f;
      --line: rgba(23,32,42,0.12);
      --accent: #0b6bcb;
      --selection: rgba(0, 120, 215, 0.28);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #13171c;
        --surface: rgba(22,27,34,0.94);
        --text: #edf2f7;
        --muted: #a9b4c0;
        --line: rgba(237,242,247,0.12);
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top, rgba(11,107,203,0.12), transparent 38%), var(--bg);
      color: var(--text);
      font-family: "Segoe UI", sans-serif;
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      padding: 12px 18px;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(14px);
    }
    .badge {
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      font-size: 13px;
      font-weight: 700;
    }
    .meta { color: var(--muted); font-size: 14px; }
    .searchbar {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-left: auto;
      padding: 6px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.55);
    }
    @media (prefers-color-scheme: dark) {
      .searchbar {
        background: rgba(255,255,255,0.04);
      }
    }
    .searchbar input {
      width: min(38vw, 280px);
      border: 0;
      outline: none;
      background: transparent;
      color: var(--text);
      font-size: 14px;
    }
    .searchbar button {
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      padding: 6px 10px;
      font-size: 12px;
      cursor: pointer;
    }
    .searchbar button.secondary {
      background: transparent;
      color: var(--text);
      border: 1px solid var(--line);
    }
    .searchbar .count {
      color: var(--muted);
      font-size: 12px;
      min-width: 54px;
      text-align: right;
    }
    #viewer {
      padding: 24px;
      display: flex;
      justify-content: center;
    }
    .page-wrap {
      position: relative;
      display: inline-block;
      background: white;
      box-shadow: 0 16px 40px rgba(0,0,0,0.18);
    }
    canvas {
      display: block;
      max-width: min(96vw, 1240px);
      height: auto;
    }
    .textLayer {
      position: absolute;
      inset: 0;
      overflow: hidden;
      line-height: 1;
    }
    .overlayLayer {
      position: absolute;
      inset: 0;
      overflow: hidden;
      pointer-events: none;
    }
    .textLayer span {
      position: absolute;
      white-space: pre;
      transform-origin: 0 0;
      color: transparent;
      user-select: text;
      cursor: text;
    }
    .textLayer span span {
      position: static;
      transform: none;
    }
    .textLayer .highlight {
      background: rgba(0, 120, 215, 0.82);
      color: #ffffff !important;
      border-radius: 2px;
      box-shadow: 0 0 0 1px rgba(255,255,255,0.18) inset;
      text-shadow: none;
    }
    .textLayer ::selection {
      background: rgba(0, 120, 215, 0.82);
      color: #ffffff;
    }
    .error {
      margin: 24px auto;
      width: min(900px, calc(100vw - 32px));
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 20px;
      box-shadow: 0 16px 40px rgba(0,0,0,0.12);
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--muted);
    }
    .match-overlay {
      position: absolute;
      background: rgba(0, 120, 215, 0.24);
      border-radius: 2px;
      box-shadow: inset 0 0 0 1px rgba(0, 120, 215, 0.12);
    }
  </style>
</head>
<body>
  <div class="topbar">
    <span class="badge" id="pageLabel"></span>
    <strong id="fileLabel"></strong>
    <span class="meta" id="queryLabel"></span>
    <div class="searchbar">
      <input id="searchInput" type="text" placeholder="페이지 내 검색" />
      <button id="searchButton" type="button">검색</button>
      <button id="prevButton" class="secondary" type="button">이전</button>
      <button id="nextButton" class="secondary" type="button">다음</button>
      <span id="searchCount" class="count"></span>
    </div>
  </div>
  <div id="viewer">
    <div class="page-wrap">
      <canvas id="pdfCanvas"></canvas>
      <div id="overlayLayer" class="overlayLayer"></div>
      <div id="textLayer" class="textLayer"></div>
    </div>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
  <script>
    const payloadBytes = Uint8Array.from(atob("__PAYLOAD__"), ch => ch.charCodeAt(0));
    const payload = JSON.parse(new TextDecoder("utf-8").decode(payloadBytes));
    const pdfBytes = Uint8Array.from(atob(payload.pdf_base64), ch => ch.charCodeAt(0));
    const pageNumber = payload.page_number;
    const query = payload.query || "";
    const fileName = payload.file_name || "PDF";
    let currentMatches = [];
    let currentMatchIndex = -1;
    let renderedItems = [];

    document.getElementById("pageLabel").textContent = `${pageNumber}페이지`;
    document.getElementById("fileLabel").textContent = fileName;
    document.getElementById("queryLabel").textContent = query ? `검색어: ${query}` : "";
    document.getElementById("searchInput").value = query;

    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

    function selectMatchText(node) {
      if (!node) return;
      window.focus();
      document.body.tabIndex = -1;
      document.body.focus();
      const selection = window.getSelection();
      if (!selection) return;
      const range = document.createRange();
      range.selectNodeContents(node);
      selection.removeAllRanges();
      selection.addRange(range);
      node.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function resetSpan(span) {
      const originalText = span.dataset.originalText;
      if (typeof originalText !== "string") return;
      span.textContent = originalText;
    }

    function clearHighlights() {
      const spans = Array.from(document.querySelectorAll("#textLayer > span"));
      for (const span of spans) {
        resetSpan(span);
      }
      document.getElementById("overlayLayer").innerHTML = "";
      currentMatches = [];
      currentMatchIndex = -1;
      document.getElementById("searchCount").textContent = "";
      window.getSelection()?.removeAllRanges();
    }

    function measureSubstringRatio(fullText, subText, span) {
      const computed = window.getComputedStyle(span);
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      ctx.font = `${computed.fontSize} ${computed.fontFamily}`;
      const fullWidth = ctx.measureText(fullText).width || 1;
      const subWidth = ctx.measureText(subText).width;
      return subWidth / fullWidth;
    }

    function createHighlightOverlay(itemInfo, matchStart, matchLength) {
      const { text, left, width, span } = itemInfo;
      const beforeText = text.slice(0, matchStart);
      const matchText = text.slice(matchStart, matchStart + matchLength);
      const beforeRatio = measureSubstringRatio(text, beforeText, span);
      const matchRatio = measureSubstringRatio(text, matchText, span);
      const textLayerRect = document.getElementById("textLayer").getBoundingClientRect();
      const spanRect = span.getBoundingClientRect();
      const verticalPadding = Math.max(1.5, spanRect.height * 0.12);
      const overlayTop = Math.max(0, spanRect.top - textLayerRect.top - verticalPadding * 0.03);
      const overlayHeight = Math.max(8, spanRect.height + verticalPadding * 1.55);

      const overlay = document.createElement("div");
      overlay.className = "match-overlay";
      overlay.style.left = `${left + width * beforeRatio}px`;
      overlay.style.top = `${overlayTop}px`;
      overlay.style.width = `${Math.max(1, width * matchRatio)}px`;
      overlay.style.height = `${overlayHeight}px`;
      return overlay;
    }

    function focusMatch(index) {
      if (!currentMatches.length) return;
      currentMatchIndex = ((index % currentMatches.length) + currentMatches.length) % currentMatches.length;
      const match = currentMatches[currentMatchIndex];
      document.getElementById("searchCount").textContent = `${currentMatchIndex + 1}/${currentMatches.length}`;
      selectMatchText(match);
    }

    function applySearch(term) {
      clearHighlights();
      const trimmed = (term || "").trim();
      if (!trimmed) return;

      const lowerTerm = trimmed.toLocaleLowerCase();
      const overlayLayer = document.getElementById("overlayLayer");

      for (const itemInfo of renderedItems) {
        const text = itemInfo.text || "";
        const lowerText = text.toLocaleLowerCase();
        const matchIndex = lowerText.indexOf(lowerTerm);
        if (matchIndex === -1) continue;

        const match = text.slice(matchIndex, matchIndex + trimmed.length);
        const overlay = createHighlightOverlay(itemInfo, matchIndex, match.length);
        overlayLayer.appendChild(overlay);
        currentMatches.push(overlay);
      }

      if (currentMatches.length) {
        focusMatch(0);
      } else {
        document.getElementById("searchCount").textContent = "0건";
      }
    }

    async function render() {
      const loadingTask = pdfjsLib.getDocument({ data: pdfBytes });
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1.6 });
      const canvas = document.getElementById("pdfCanvas");
      const context = canvas.getContext("2d");
      const textLayer = document.getElementById("textLayer");
      const overlayLayer = document.getElementById("overlayLayer");

      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = viewport.width + "px";
      canvas.style.height = viewport.height + "px";
      textLayer.style.width = viewport.width + "px";
      textLayer.style.height = viewport.height + "px";
      overlayLayer.style.width = viewport.width + "px";
      overlayLayer.style.height = viewport.height + "px";
      textLayer.innerHTML = "";
      overlayLayer.innerHTML = "";
      renderedItems = [];

      await page.render({ canvasContext: context, viewport }).promise;

      const textContent = await page.getTextContent();
      for (const item of textContent.items) {
        const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
        const span = document.createElement("span");
        span.textContent = item.str;
        span.dataset.originalText = item.str;
        span.style.left = `${tx[4]}px`;
        span.style.top = `${tx[5] - item.height * viewport.scale}px`;
        span.style.fontSize = `${item.height * viewport.scale}px`;
        span.style.fontFamily = item.fontName || "sans-serif";
        span.style.transform = `scaleX(${tx[0] / (item.height || 1)})`;
        textLayer.appendChild(span);
        renderedItems.push({
          text: item.str,
          left: tx[4],
          top: tx[5] - item.height * viewport.scale,
          width: item.width * viewport.scale,
          height: item.height * viewport.scale,
          span,
        });
      }

      applySearch(query);
    }

    document.getElementById("searchButton").addEventListener("click", () => {
      applySearch(document.getElementById("searchInput").value);
    });

    document.getElementById("searchInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applySearch(event.currentTarget.value);
      }
    });

    document.getElementById("prevButton").addEventListener("click", () => {
      if (currentMatches.length) {
        focusMatch(currentMatchIndex - 1);
      }
    });

    document.getElementById("nextButton").addEventListener("click", () => {
      if (currentMatches.length) {
        focusMatch(currentMatchIndex + 1);
      }
    });

    window.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        const input = document.getElementById("searchInput");
        input.focus();
        input.select();
      }
    });

    render().catch((error) => {
      document.body.innerHTML = `
        <div class="error">
          <strong>PDF를 여는 중 오류가 발생했습니다.</strong>
          <pre>${String(error)}</pre>
        </div>
      `;
    });
  </script>
</body>
</html>
"""


def ensure_state() -> None:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "login_failures" not in st.session_state:
        st.session_state.login_failures = 0
    if "lockout_until" not in st.session_state:
        st.session_state.lockout_until = 0.0
    if "index_data" not in st.session_state:
        st.session_state.index_data = None
    if "index_source" not in st.session_state:
        st.session_state.index_source = ""
    if "folder_input" not in st.session_state:
        st.session_state.folder_input = ""
    if "folder_input_pending" not in st.session_state:
        st.session_state.folder_input_pending = ""
    if "source_folder" not in st.session_state:
        st.session_state.source_folder = ""
    if "source_folder_pending" not in st.session_state:
        st.session_state.source_folder_pending = ""
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

    if st.session_state.source_folder_pending:
        st.session_state.source_folder = st.session_state.source_folder_pending
        st.session_state.source_folder_pending = ""

    if st.session_state.search_input_pending:
        st.session_state.search_input = st.session_state.search_input_pending
        st.session_state.search_input_pending = ""

    settings = load_settings(SETTINGS_FILE)
    if not st.session_state.folder_input:
        last_folder = settings.get("last_folder", "")
        if isinstance(last_folder, str):
            st.session_state.folder_input = last_folder
    if not st.session_state.source_folder:
        source_folder = settings.get("source_folder", "")
        if isinstance(source_folder, str):
            st.session_state.source_folder = source_folder
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


def render_login_gate() -> bool:
    expected_username, expected_password = get_auth_credentials()
    max_attempts, lockout_minutes = get_auth_settings()

    if not expected_username or not expected_password:
        st.error("로그인 정보가 설정되지 않았습니다.")
        st.caption("배포 환경에서는 Streamlit secrets 또는 환경변수에 `APP_USERNAME`, `APP_PASSWORD`를 설정해야 합니다.")
        return False

    if st.session_state.authenticated:
        return True

    access_token = st.query_params.get("access_token", "")
    if is_valid_app_access_token(access_token):
        st.session_state.authenticated = True
        return True

    now = time.time()
    if st.session_state.lockout_until > now:
        remaining_seconds = int(st.session_state.lockout_until - now)
        remaining_minutes = max(1, (remaining_seconds + 59) // 60)
        st.title("PDF Searcher")
        st.error(f"로그인 시도가 너무 많아 잠시 잠겼습니다. 약 {remaining_minutes}분 후 다시 시도해 주세요.")
        return False

    st.title("PDF Searcher")
    st.caption("아이디와 비밀번호를 입력해야 사용할 수 있습니다.")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")

    if submitted:
        if check_credentials(username.strip(), password):
            st.session_state.authenticated = True
            st.session_state.login_failures = 0
            st.session_state.lockout_until = 0.0
            st.rerun()
        st.session_state.login_failures += 1
        remaining_attempts = max_attempts - st.session_state.login_failures
        if remaining_attempts <= 0:
            st.session_state.lockout_until = time.time() + (lockout_minutes * 60)
            st.session_state.login_failures = 0
            st.error(f"로그인 실패 횟수를 초과했습니다. {lockout_minutes}분 후 다시 시도해 주세요.")
            return False
        st.error(f"아이디 또는 비밀번호가 올바르지 않습니다. 남은 시도 {remaining_attempts}회")

    return False


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


def save_uploaded_originals(files) -> int:
    UPLOADED_ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    saved_count = 0
    for file in files:
        target = UPLOADED_ORIGINALS_DIR / file.name
        target.write_bytes(file.getbuffer())
        saved_count += 1
    return saved_count


def get_source_folder() -> Path | None:
    source_folder = st.session_state.get("source_folder", "")
    if source_folder:
        source_path = Path(source_folder)
        if source_path.exists() and source_path.is_dir():
            return source_path.resolve()

    settings = load_settings(SETTINGS_FILE)
    stored_source_folder = settings.get("source_folder", "")
    if isinstance(stored_source_folder, str) and stored_source_folder:
        source_path = Path(stored_source_folder)
        if source_path.exists() and source_path.is_dir():
            return source_path.resolve()
    return None


def resolve_pdf_path(file_path: str, file_name: str) -> Path | None:
    candidates: list[Path] = []
    if file_path:
        candidates.append(Path(file_path))
    if file_name:
        candidates.append(Path.cwd() / file_name)
        candidates.append(UPLOADED_ORIGINALS_DIR / file_name)
    source_folder = get_source_folder()
    if source_folder is not None and file_name:
        candidates.append(source_folder / file_name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    if file_name:
        if UPLOADED_ORIGINALS_DIR.exists():
            matches = list(UPLOADED_ORIGINALS_DIR.rglob(file_name))
            if matches:
                return matches[0].resolve()
        if source_folder is not None:
            matches = list(source_folder.rglob(file_name))
            if matches:
                return matches[0].resolve()
        matches = list(Path.cwd().rglob(file_name))
        if matches:
            return matches[0].resolve()
    return None


def render_pdf_viewer_mode() -> bool:
    if st.query_params.get("viewer") != "1":
        return False

    file_path = st.query_params.get("path", "")
    file_name = st.query_params.get("file_name", "")
    query = st.query_params.get("query", "")
    access_token = st.query_params.get("access_token", "")
    page_raw = st.query_params.get("page", "1")

    try:
        page_number = max(1, int(page_raw))
    except ValueError:
        page_number = 1

    resolved_path = resolve_pdf_path(file_path, file_name)
    st.set_page_config(page_title="PDF Viewer", page_icon="PDF", layout="wide")

    if not is_valid_viewer_access_token(file_path, file_name, page_number, query, access_token):
        st.error("원본 파일 링크 인증이 유효하지 않습니다.")
        st.caption("검색 결과 화면에서 다시 원본 보기 링크를 눌러 주세요.")
        return True

    if resolved_path is None:
        st.error("PDF 파일을 찾을 수 없습니다.")
        st.caption("배포 환경에서는 현재 앱 서버에 존재하는 PDF만 열 수 있습니다.")
        return True

    payload = {
        "pdf_base64": base64.b64encode(resolved_path.read_bytes()).decode("ascii"),
        "page_number": page_number,
        "query": query,
        "file_name": resolved_path.name,
    }
    payload_b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")

    components.html(
        VIEWER_HTML_TEMPLATE.replace("__PAYLOAD__", payload_b64),
        height=1200,
        scrolling=True,
    )
    return True


def render_result_card(result: dict, query: str) -> None:
    resolved_pdf = resolve_pdf_path(result["file_path"], result["file_name"])
    viewer_link = None
    if resolved_pdf is not None:
        access_token = build_viewer_access_token(
            str(resolved_pdf),
            result["file_name"],
            result["page_number"],
            query,
        )
        viewer_link = build_pdf_viewer_link(
            str(resolved_pdf),
            result["file_name"],
            result["page_number"],
            query,
            result["x"],
            result["y"],
            result["font_size"],
            access_token=access_token,
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
    st.markdown(RESULT_BOX_STYLE, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="result-snippet-box">
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
            st.caption("원본 파일을 찾지 못했습니다. 사이드바의 `원본 PDF 폴더`를 지정하면 같은 파일명 기준으로 찾아 열 수 있습니다.")
        st.write("확장 문맥")
        st.markdown(
            f"""
            <div class="result-snippet-box">
                {highlight_query(result["context_snippet"], query)}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    with st.sidebar:
        if st.button("로그아웃", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.login_failures = 0
            st.session_state.lockout_until = 0.0
            st.rerun()

        st.divider()
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

        st.divider()
        st.subheader("원본 파일 위치")
        source_folder = st.text_input(
            "원본 PDF 폴더",
            key="source_folder",
            placeholder=r"C:\Users\user\Documents\pdfs",
            help="로컬 실행에서는 이 폴더 아래에서 같은 파일명을 찾아 원본 보기 링크를 만듭니다.",
        )
        if tk is not None and filedialog is not None:
            if st.button("원본 폴더 선택", use_container_width=True):
                selected = choose_folder()
                if selected:
                    st.session_state.source_folder_pending = selected
                    update_settings(SETTINGS_FILE, {"source_folder": selected})
                    st.rerun()
        else:
            st.caption("이 배포 환경에서는 폴더 선택 창을 지원하지 않아 경로를 직접 입력해야 합니다.")

        if source_folder.strip():
            update_settings(SETTINGS_FILE, {"source_folder": source_folder.strip()})

        original_uploads = st.file_uploader(
            "또는 원본 PDF 업로드",
            type=["pdf"],
            accept_multiple_files=True,
            help="배포 환경에서는 사용자 PC 폴더에 직접 접근할 수 없으므로, 원본 보기가 필요하면 PDF를 여기에 업로드해 주세요.",
        )
        if st.button("업로드한 원본 저장", use_container_width=True):
            if not original_uploads:
                st.error("하나 이상의 원본 PDF를 업로드해 주세요.")
            else:
                saved_count = save_uploaded_originals(original_uploads)
                st.success(f"{saved_count}개 원본 PDF를 앱 서버에 저장했습니다.")

        if st.button("폴더 색인 생성", use_container_width=True):
            if not folder.strip():
                st.error("PDF 폴더 경로를 입력해 주세요.")
            else:
                folder_path = Path(folder).expanduser()
                if not folder_path.exists():
                    st.error("입력한 폴더를 찾을 수 없습니다.")
                else:
                    update_settings(
                        SETTINGS_FILE,
                        {
                            "last_folder": str(folder_path.resolve()),
                            "source_folder": str(folder_path.resolve()),
                        },
                    )
                    st.session_state.source_folder = str(folder_path.resolve())
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
    access_token = build_app_access_token()
    for term in recent_searches:
        encoded = quote(term)
        chips.append(
            f'<span class="recent-chip">'
            f'<form class="recent-chip-form" method="get">'
            f'<input type="hidden" name="recent_action" value="search">'
            f'<input type="hidden" name="recent_value" value="{html.escape(term)}">'
            f'<input type="hidden" name="access_token" value="{html.escape(access_token)}">'
            f'<button type="submit" class="recent-chip-term">{html.escape(term)}</button>'
            f"</form>"
            f'<form class="recent-chip-form" method="get">'
            f'<input type="hidden" name="recent_action" value="delete">'
            f'<input type="hidden" name="recent_value" value="{html.escape(term)}">'
            f'<input type="hidden" name="access_token" value="{html.escape(access_token)}">'
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

    if render_pdf_viewer_mode():
        return

    if not render_login_gate():
        return

    process_recent_search_action()
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
