param(
    [string]$Message = "Update app"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$remoteUrl = "https://github.com/lovin74-afk/pdf-search.git"

$hasOrigin = git remote | Select-String -Pattern "^origin$" -Quiet
if (-not $hasOrigin) {
    git remote add origin $remoteUrl
}

# Stop tracking local-only app data if it was committed in the past.
git rm --cached -r .pdf_search_index 2>$null
git rm --cached -r __pycache__ 2>$null
git rm --cached -r pdf_searcher/__pycache__ 2>$null
git rm --cached -r tests/__pycache__ 2>$null

git add -A
git commit -m $Message
git push -u origin main
