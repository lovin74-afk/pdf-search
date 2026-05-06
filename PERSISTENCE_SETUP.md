# 휴면 복구 후에도 색인/원본 PDF 유지하기

Streamlit Community Cloud의 로컬 파일 시스템은 영구 저장소가 아닙니다.  
앱이 오래 쉬었다가 다시 깨어나면 `.pdf_search_index/` 와 `.uploaded_originals/` 안의 파일이 사라질 수 있습니다.

이 프로젝트는 그 문제를 막기 위해, 아래 데이터를 GitHub 저장소 안의 ZIP 백업 파일로 자동 저장/복원하도록 되어 있습니다.

- 색인 DB: `.pdf_search_index/indexes.db`
- 설정 파일: `.pdf_search_index/settings.json`
- 업로드한 원본 PDF: `.uploaded_originals/`

## 1. Streamlit Cloud Secrets 설정

앱의 `Settings` -> `Secrets`에 아래 값을 넣어 주세요.

```toml
GITHUB_STATE_TOKEN = "your-github-token"
GITHUB_STATE_REPO = "lovin74-afk/pdf-search"
GITHUB_STATE_BRANCH = "main"
GITHUB_STATE_PATH = ".streamlit-state/app_state.zip"
```

기본값:

- `GITHUB_STATE_REPO`: `lovin74-afk/pdf-search`
- `GITHUB_STATE_BRANCH`: `main`
- `GITHUB_STATE_PATH`: `.streamlit-state/app_state.zip`

즉, 토큰만 넣어도 기본 저장소 기준으로는 동작합니다.

## 2. GitHub 토큰 권한

토큰은 최소한 대상 저장소에 파일을 읽고/쓰는 권한이 있어야 합니다.

- 저장소 내용 읽기
- 저장소 내용 쓰기

가장 간단한 방법은 이 저장소에 접근 가능한 토큰을 하나 만들어 `GITHUB_STATE_TOKEN`으로 넣는 것입니다.

## 3. 동작 방식

앱이 시작될 때:

- GitHub의 `.streamlit-state/app_state.zip` 이 있으면 먼저 내려받아 복원합니다.

아래 작업이 일어날 때:

- 새 색인을 DB에 저장할 때
- 원본 PDF를 업로드해 저장할 때
- 최근 검색어/원본 폴더/마지막 폴더 같은 설정이 바뀔 때

앱 상태를 다시 ZIP으로 만들어 GitHub에 덮어씁니다.

## 4. 주의할 점

- 원본 PDF가 많거나 매우 크면 백업 ZIP도 커질 수 있습니다.
- 업로드 직후 바로 앱을 닫기보다, 저장 완료 메시지가 뜰 때까지 기다리는 것이 안전합니다.
- GitHub 토큰이 없으면 앱은 기존처럼 동작하지만, 휴면 후 데이터 유지 기능은 꺼진 상태가 됩니다.
