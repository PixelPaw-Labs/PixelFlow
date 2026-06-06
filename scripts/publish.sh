#!/usr/bin/env bash
#
# Publish PixelFlow to PyPI from your local machine.
#
# Usage:
#   scripts/publish.sh            # build, check, and upload to PyPI
#   scripts/publish.sh --test     # upload to TestPyPI instead (dry run)
#   scripts/publish.sh --build    # build + twine check only, no upload
#
# Authentication (pick one — the script never stores or echoes your token):
#   1. Export a token for this shell:
#        export TWINE_USERNAME=__token__
#        export TWINE_PASSWORD=pypi-XXXXXXXX      # your PyPI API token
#   2. Or configure ~/.pypirc once.
#   3. Or just run it and twine will prompt interactively.
#
# Prefers `uv` (manages its own Python + build/twine, no setup needed).
# Falls back to PYTHON=/path/to/python with pip if uv is not installed.

set -euo pipefail

cd "$(dirname "$0")/.."

REPO_ARGS=()
DO_UPLOAD=1

for arg in "$@"; do
  case "$arg" in
    --test)
      REPO_ARGS=(--repository testpypi)
      echo "→ Target: TestPyPI"
      ;;
    --build)
      DO_UPLOAD=0
      echo "→ Build + check only (no upload)"
      ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

# Read name/version straight from pyproject.toml (no Python interpreter needed).
DIST_NAME="$(sed -n 's/^name = "\(.*\)"/\1/p' pyproject.toml | head -n1)"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n1)"
echo "→ Package: ${DIST_NAME} ${VERSION}"

# Refuse to publish a version that already exists on PyPI (PyPI rejects
# re-uploads, so catch it early before building).
if [ "$DO_UPLOAD" -eq 1 ] && [ "${#REPO_ARGS[@]}" -eq 0 ]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/${DIST_NAME}/${VERSION}/json" || echo 000)"
  if [ "$code" = "200" ]; then
    echo "✗ ${DIST_NAME} ${VERSION} already exists on PyPI. Bump the version in" >&2
    echo "  pyproject.toml and update CHANGELOG.md before publishing." >&2
    exit 1
  fi
fi

rm -rf dist/

if command -v uv >/dev/null 2>&1; then
  echo "→ Building with uv"
  uv build
  echo "→ Validating distributions"
  uv tool run twine check dist/*
  if [ "$DO_UPLOAD" -eq 1 ]; then
    echo "→ Uploading"
    uv tool run twine upload "${REPO_ARGS[@]}" dist/*
  fi
else
  PYTHON="${PYTHON:-python3}"
  echo "→ uv not found; using ${PYTHON} ($("$PYTHON" --version 2>&1))"
  if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    echo "✗ ${PYTHON} has no pip. Install uv (https://docs.astral.sh/uv/) or" >&2
    echo "  point PYTHON at an interpreter that has pip." >&2
    exit 1
  fi
  "$PYTHON" -m pip install --upgrade --quiet build twine
  echo "→ Building"
  "$PYTHON" -m build
  echo "→ Validating distributions"
  "$PYTHON" -m twine check dist/*
  if [ "$DO_UPLOAD" -eq 1 ]; then
    echo "→ Uploading"
    "$PYTHON" -m twine upload "${REPO_ARGS[@]}" dist/*
  fi
fi

if [ "$DO_UPLOAD" -eq 0 ]; then
  echo "✓ Built and validated. Artifacts in dist/:"
  ls -1 dist/
  exit 0
fi

echo "✓ Published ${DIST_NAME} ${VERSION}"
if [ "${#REPO_ARGS[@]}" -eq 0 ]; then
  echo "  Verify: pipx install ${DIST_NAME} && pixelflow --version"
else
  echo "  Verify: pipx install --index-url https://test.pypi.org/simple/ ${DIST_NAME}"
fi
