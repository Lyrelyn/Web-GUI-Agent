[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/ and run this script again."
}

uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run mypy src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pyright
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pytest
exit $LASTEXITCODE
