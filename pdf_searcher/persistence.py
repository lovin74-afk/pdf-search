from __future__ import annotations

import base64
import io
import os
import zipfile
from pathlib import Path

import requests


def _get_repo() -> str:
    return str(os.getenv("GITHUB_STATE_REPO", "lovin74-afk/pdf-search")).strip()


def _get_branch() -> str:
    return str(os.getenv("GITHUB_STATE_BRANCH", "main")).strip()


def _get_token() -> str:
    return str(os.getenv("GITHUB_STATE_TOKEN", "")).strip()


def _get_state_path() -> str:
    return str(os.getenv("GITHUB_STATE_PATH", ".streamlit-state/app_state.zip")).strip()


def is_persistence_configured() -> bool:
    return bool(_get_repo() and _get_branch() and _get_token())


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Accept": "application/vnd.github+json",
    }


def _contents_url() -> str:
    return f"https://api.github.com/repos/{_get_repo()}/contents/{_get_state_path()}"


def _zip_state(index_dir: Path, uploads_dir: Path, settings_file: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        if settings_file.exists():
            zip_file.write(settings_file, settings_file.as_posix())
        if index_dir.exists():
            for path in index_dir.rglob("*"):
                if path.is_file():
                    zip_file.write(path, path.as_posix())
        if uploads_dir.exists():
            for path in uploads_dir.rglob("*"):
                if path.is_file():
                    zip_file.write(path, path.as_posix())
    return buffer.getvalue()


def backup_state_to_github(index_dir: Path, uploads_dir: Path, settings_file: Path) -> bool:
    if not is_persistence_configured():
        return False

    zip_bytes = _zip_state(index_dir, uploads_dir, settings_file)
    existing_sha = None

    response = requests.get(_contents_url(), headers=_headers(), params={"ref": _get_branch()}, timeout=30)
    if response.status_code == 200:
        existing_sha = response.json().get("sha")
    elif response.status_code not in {404}:
        return False

    payload = {
        "message": "Update Streamlit app state backup",
        "content": base64.b64encode(zip_bytes).decode("ascii"),
        "branch": _get_branch(),
    }
    if existing_sha:
        payload["sha"] = existing_sha

    upload_response = requests.put(_contents_url(), headers=_headers(), json=payload, timeout=30)
    return upload_response.status_code in {200, 201}


def restore_state_from_github(index_dir: Path, uploads_dir: Path, settings_file: Path) -> bool:
    if not is_persistence_configured():
        return False

    response = requests.get(_contents_url(), headers=_headers(), params={"ref": _get_branch()}, timeout=30)
    if response.status_code != 200:
        return False

    payload = response.json()
    content = payload.get("content", "")
    if not content:
        return False

    zip_bytes = base64.b64decode(content)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zip_file:
        for member in zip_file.infolist():
            target = Path(member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zip_file.read(member))
    return settings_file.exists() or index_dir.exists() or uploads_dir.exists()
