#!/usr/bin/env bash
# Rebuilds a book's website and pushes it to a GitHub repository's gh-pages
# branch, replacing what was there (the branch keeps no history).
#   scripts/publish.sh BOOK REPO_URL
#   scripts/publish.sh slomannyj_mech git@github.com:USER/slomannyj-mech.git
# Then, once: the repository's Settings → Pages → Branch: gh-pages, / (root).
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 BOOK REPO_URL" >&2
  exit 2
fi
book="$1" repo="$2"
root="$(cd "$(dirname "$0")/.." && pwd)"

"$root/.venv/bin/python" -m bookgraph render "$book"
"$root/.venv/bin/python" -m bookgraph site "$book"

# A throwaway copy: the site folder is rebuilt from scratch every time.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -a "$root/out/$book/site/." "$tmp/"
cd "$tmp"
git init -q -b gh-pages
git add -A
git commit -q -m "Site for $book, $(date '+%Y-%m-%d %H:%M')"
git push -f "$repo" gh-pages
echo "pushed $(git ls-files | wc -l) files to $repo (gh-pages)"
