# Remove PDFs From GitHub

이 작업은 로컬 PDF 파일은 그대로 두고, GitHub 저장소에서만 PDF를 제거합니다.

## 실행

```powershell
powershell -ExecutionPolicy Bypass -File .\remove_pdfs_from_github.ps1 -Message "Remove PDF files from repository"
```

## 동작

- 현재 Git이 추적 중인 `*.pdf` 파일을 찾습니다.
- `git rm --cached -- '*.pdf'`로 Git 추적만 해제합니다.
- 로컬 파일은 삭제하지 않습니다.
- `.gitignore`에 `*.pdf`가 있어 이후 PDF가 다시 올라가지 않게 합니다.

## 참고

이 방법은 현재 브랜치 기준으로 PDF를 저장소에서 없애는 방법입니다.
예전 커밋 히스토리에서까지 완전히 지우려면 별도의 히스토리 정리가 필요합니다.
