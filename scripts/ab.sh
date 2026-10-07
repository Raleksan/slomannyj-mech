#!/usr/bin/env bash
# The model A/B test on an A6000 host: the gold sample through the original
# Qwen3.8-27B, then the abliterated one, both at Q8_0, then the comparison.
#   scripts/ab.sh [-p PORT] USER@HOST BOOK
#   scripts/ab.sh ubuntu@69.19.140.71 slomannyj_mech
# Sets the host up with scripts/deploy.sh for each model (a6000-original,
# then a6000-q8), copies the book's chapters and chunks there, runs
# bookgraph ab, and copies work/BOOK/ab/ back. Run it again after a dropped
# connection: finished chunks and installed models are skipped.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port=22
while getopts p: opt; do
  case "$opt" in
    p) port="$OPTARG" ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [[ $# -ne 2 ]]; then
  echo "usage: $0 [-p PORT] USER@HOST BOOK" >&2
  exit 2
fi
host="$1" book="$2"
work="${root}/work/${book}"

for profile in a6000-original a6000-q8; do
  echo "== ${profile}"
  "${root}/scripts/deploy.sh" -p "$port" "$host" "$profile"
  ssh -p "$port" "$host" "mkdir -p book-graph/work/${book}"
  rsync -az -e "ssh -p ${port}" "${work}/chapters.json" "${work}/chunks.json" \
    "${host}:book-graph/work/${book}/"
  ssh -p "$port" "$host" "cd book-graph && .venv/bin/python -m bookgraph ab ${book} -j 3"
  rsync -az -e "ssh -p ${port}" "${host}:book-graph/work/${book}/ab/" "${work}/ab/"
done
"${root}/.venv/bin/python" -m bookgraph ab "$book" --report
