param(
    [string]$Message = "Update app"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$remoteUrl = "https://github.com/lovin74-afk/pdf-search.git"

function Remove-TrackedPathIfExists {
    param(
        [string]$PathSpec
    )

    $tracked = @(git ls-files -- $PathSpec 2>$null)
    if ($tracked.Count -gt 0) {
        git rm --cached -r -- $PathSpec
    }
}

$hasOrigin = git remote | Select-String -Pattern "^origin$" -Quiet
if (-not $hasOrigin) {
    git remote add origin $remoteUrl
}

# Stop tracking local-only app data if it was committed in the past.
Remove-TrackedPathIfExists ".pdf_search_index"
Remove-TrackedPathIfExists "__pycache__"
Remove-TrackedPathIfExists "pdf_searcher/__pycache__"
Remove-TrackedPathIfExists "tests/__pycache__"

git add -A
git commit -m $Message
git push -u origin main
