# Remove PDFs From Git History

현재 브랜치에서 PDF를 안 보이게 하는 것과, Git 히스토리 전체에서 PDF를 완전히 지우는 것은 다릅니다.

이 문서는 `*.pdf` 파일을 Git 히스토리 전체에서 제거하는 방법을 정리한 것입니다.

## 주의

- 이 작업은 Git 히스토리를 다시 씁니다.
- 이미 저장소를 받은 다른 사람은 다시 동기화가 필요합니다.
- 잘못하면 다른 파일 이력까지 바뀔 수 있으니 백업 또는 새 브랜치에서 먼저 확인하는 것이 좋습니다.

## 권장 방법

`git-filter-repo`를 사용하는 방법이 가장 안정적입니다.

## 1. 먼저 현재 저장소 화면에서 PDF 제거

아직 안 했다면 먼저 아래를 실행해 현재 브랜치에서 PDF를 제거합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\remove_pdfs_from_github.ps1 -Message "Remove PDF files from repository"
```

## 2. git-filter-repo 설치

Python이 있다면 보통 아래로 설치할 수 있습니다.

```powershell
python -m pip install git-filter-repo
```

설치 확인:

```powershell
git filter-repo --help
```

## 3. 작업 전 백업 브랜치 생성

```powershell
git branch backup-before-pdf-cleanup
```

## 4. 히스토리 전체에서 PDF 제거

프로젝트 폴더에서 실행:

```powershell
git filter-repo --path-glob *.pdf --invert-paths
```

이 명령은 모든 커밋에서 `*.pdf`를 제거합니다.

## 5. 원격 다시 연결

`git filter-repo` 실행 후 원격이 제거될 수 있으므로 다시 연결합니다.

```powershell
git remote add origin https://github.com/lovin74-afk/pdf-search.git
```

이미 있으면 생략합니다.

## 6. 강제 푸시

```powershell
git push --force origin main
```

태그나 다른 브랜치도 정리해야 하면 별도 작업이 필요합니다.

## 7. GitHub에서 확인할 점

- 저장소 Code 화면에서 PDF가 사라졌는지 확인
- Releases, tags, other branches에 PDF가 남아 있는지 확인
- Streamlit 배포가 계속 필요한 파일만 가지고 정상 실행되는지 확인

## 참고

이 작업 후에도 GitHub에서 큰 파일 사용량이 바로 줄지 않을 수 있습니다.
그러나 새 히스토리 기준으로는 PDF가 제외됩니다.

완전히 정리한 뒤에는 저장소를 새로 clone 받는 것이 가장 깔끔합니다.
