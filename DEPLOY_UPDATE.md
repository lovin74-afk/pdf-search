# GitHub / Streamlit Update

`tkinter` 없는 배포 환경에서도 앱이 실행되도록 수정했습니다.

## 한 번에 반영하기

프로젝트 폴더에서 아래처럼 실행하면 됩니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\publish_to_github.ps1 -Message "Fix Streamlit Cloud tkinter import"
```

스크립트는 전체 변경사항을 커밋하고 푸시합니다.
또한 `.pdf_search_index/`, `__pycache__/` 같은 로컬 전용 파일이 예전에 Git에 올라가 있었더라도 자동으로 추적 해제합니다.

## 수동으로 반영하기

```powershell
git remote add origin https://github.com/lovin74-afk/pdf-search.git
git rm --cached -r .pdf_search_index __pycache__ pdf_searcher/__pycache__ tests/__pycache__
git add -A
git commit -m "Fix Streamlit Cloud tkinter import"
git push -u origin main
```

`origin`이 이미 있으면 `git remote add origin ...`는 생략하면 됩니다.

GitHub 푸시가 끝나면 Streamlit Community Cloud에서 재배포하거나 자동 반영을 기다리면 됩니다.
