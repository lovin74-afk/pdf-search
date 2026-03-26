from __future__ import annotations

import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


_server_lock = threading.Lock()
_server_state: dict[str, object] = {"server": None, "thread": None, "base_url": None}


VIEWER_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PDF Viewer</title>
  <style>
    body { margin: 0; font-family: "Segoe UI", sans-serif; background: #f4f1ea; color: #1f2937; }
    .topbar {
      position: sticky; top: 0; z-index: 10; padding: 12px 18px; background: rgba(255,255,255,0.92);
      backdrop-filter: blur(10px); border-bottom: 1px solid #ddd6c9; display: flex; gap: 16px; align-items: center;
    }
    .badge { background: #1f2937; color: white; padding: 4px 10px; border-radius: 999px; font-size: 14px; }
    #viewer { padding: 24px; display: flex; justify-content: center; }
    .page-wrap {
      position: relative; display: inline-block; background: white; box-shadow: 0 12px 30px rgba(0,0,0,0.12);
    }
    canvas { display: block; max-width: min(96vw, 1200px); height: auto; }
    .textLayer {
      position: absolute; inset: 0; overflow: hidden; line-height: 1; opacity: 1;
    }
    .textLayer span {
      position: absolute; white-space: pre; transform-origin: 0 0; color: transparent;
      user-select: text; cursor: text;
    }
    .textLayer span span {
      position: static; transform: none;
    }
    .textLayer .highlight {
      background: rgba(0, 120, 215, 0.28);
      border-radius: 2px;
    }
    .textLayer ::selection {
      background: rgba(0, 120, 215, 0.32);
    }
    .note { color: #4b5563; font-size: 14px; }
  </style>
</head>
<body>
  <div class="topbar">
    <span class="badge" id="pageLabel"></span>
    <strong id="fileLabel"></strong>
    <span class="note" id="queryLabel"></span>
  </div>
  <div id="viewer">
    <div class="page-wrap">
      <canvas id="pdfCanvas"></canvas>
      <div id="textLayer" class="textLayer"></div>
    </div>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
  <script>
    const params = new URLSearchParams(window.location.search);
    const pdfPath = params.get("path");
    const pageNumber = Number(params.get("page") || "1");
    const query = params.get("query") || "";
    const fileName = decodeURIComponent((pdfPath || "").split(/[\\\\/]/).pop() || "PDF");

    document.getElementById("pageLabel").textContent = pageNumber + "페이지";
    document.getElementById("fileLabel").textContent = fileName;
    document.getElementById("queryLabel").textContent = query ? `검색어: ${query}` : "";

    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

    function selectMatchText(node) {
      if (!node) {
        return;
      }
      const selection = window.getSelection();
      if (!selection) {
        return;
      }
      const range = document.createRange();
      range.selectNodeContents(node);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    async function render() {
      const url = `/pdf?path=${encodeURIComponent(pdfPath || "")}`;
      const loadingTask = pdfjsLib.getDocument(url);
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1.6 });
      const canvas = document.getElementById("pdfCanvas");
      const context = canvas.getContext("2d");
      const textLayer = document.getElementById("textLayer");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = viewport.width + "px";
      canvas.style.height = viewport.height + "px";
      textLayer.style.width = viewport.width + "px";
      textLayer.style.height = viewport.height + "px";
      textLayer.innerHTML = "";

      await page.render({ canvasContext: context, viewport }).promise;

      const textContent = await page.getTextContent();
      for (const item of textContent.items) {
        const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
        const span = document.createElement("span");
        span.textContent = item.str;
        span.style.left = `${tx[4]}px`;
        span.style.top = `${tx[5] - item.height * viewport.scale}px`;
        span.style.fontSize = `${item.height * viewport.scale}px`;
        span.style.fontFamily = item.fontName || "sans-serif";
        span.style.transform = `scaleX(${tx[0] / (item.height || 1)})`;
        textLayer.appendChild(span);
      }

      if (query) {
        const lowerQuery = query.toLocaleLowerCase();
        const spans = Array.from(textLayer.querySelectorAll("span"));
        let firstMatch = null;

        for (const span of spans) {
          const text = span.textContent || "";
          const lowerText = text.toLocaleLowerCase();
          const matchIndex = lowerText.indexOf(lowerQuery);
          if (matchIndex === -1) {
            continue;
          }

          const before = text.slice(0, matchIndex);
          const match = text.slice(matchIndex, matchIndex + query.length);
          const after = text.slice(matchIndex + query.length);
          span.innerHTML = "";

          if (before) {
            const beforeNode = document.createElement("span");
            beforeNode.textContent = before;
            span.appendChild(beforeNode);
          }

          const mark = document.createElement("span");
          mark.className = "highlight";
          mark.textContent = match;
          span.appendChild(mark);

          if (after) {
            const afterNode = document.createElement("span");
            afterNode.textContent = after;
            span.appendChild(afterNode);
          }

          if (!firstMatch) {
            firstMatch = mark;
          }
        }

        if (firstMatch) {
          firstMatch.scrollIntoView({ behavior: "smooth", block: "center" });
          setTimeout(() => selectMatchText(firstMatch), 150);
        }
      }
    }

    render().catch((error) => {
      document.getElementById("viewer").innerHTML =
        `<div style="padding:24px;background:white;border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,0.08)">
          <strong>PDF를 여는 중 오류가 발생했습니다.</strong>
          <pre style="white-space:pre-wrap">${String(error)}</pre>
        </div>`;
    });
  </script>
</body>
</html>
"""


def _parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes="):
        return None

    range_spec = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
    if "-" not in range_spec:
        return None

    start_text, end_text = range_spec.split("-", 1)
    if not start_text and not end_text:
        return None

    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
    else:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            return None
        start = max(0, file_size - suffix_length)
        end = file_size - 1

    if start < 0 or end < start or start >= file_size:
        return None

    end = min(end, file_size - 1)
    return start, end


def _build_content_disposition(filename: str) -> str:
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii").strip()
    if not ascii_filename:
        ascii_filename = "document.pdf"
    encoded_filename = quote(filename, safe="")
    return f'inline; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'


class PdfFileHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/viewer":
            self._serve_viewer()
            return
        if parsed.path != "/pdf":
            self.send_error(404, "Not Found")
            return

        params = parse_qs(parsed.query)
        raw_path = params.get("path", [""])[0]
        pdf_path = Path(unquote(raw_path))
        if not pdf_path.is_absolute() or not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            self.send_error(404, "PDF Not Found")
            return

        content_type, _ = mimetypes.guess_type(str(pdf_path))
        file_size = pdf_path.stat().st_size
        byte_range = _parse_range_header(self.headers.get("Range"), file_size)

        if byte_range is None:
            start = 0
            end = file_size - 1
            self.send_response(200)
        else:
            start, end = byte_range
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")

        content_length = end - start + 1
        self.send_header("Content-Type", content_type or "application/pdf")
        self.send_header("Content-Disposition", _build_content_disposition(pdf_path.name))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(content_length))
        self.end_headers()
        with pdf_path.open("rb") as handle:
            handle.seek(start)
            remaining = content_length
            chunk_size = 64 * 1024
            while remaining > 0:
                chunk = handle.read(min(chunk_size, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _serve_viewer(self) -> None:
        body = VIEWER_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def ensure_local_pdf_server(host: str = "127.0.0.1", port: int = 8765) -> str:
    with _server_lock:
        base_url = _server_state.get("base_url")
        if isinstance(base_url, str):
            return base_url

        server = ThreadingHTTPServer((host, port), PdfFileHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        actual_base_url = f"http://{host}:{server.server_port}"
        _server_state["server"] = server
        _server_state["thread"] = thread
        _server_state["base_url"] = actual_base_url
        return actual_base_url
