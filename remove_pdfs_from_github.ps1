param(
    [string]$Message = "Remove PDF files from repository"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

# Keep local PDFs, but remove them from git tracking.
# Use git pathspec directly so Unicode filenames are handled by git, not PowerShell string piping.
git rm --cached -- '*.pdf'

git add .gitignore
git commit -m $Message
git push
