#!/usr/bin/env bash
# Shows the pipeline's progress on the GPU host, redrawn every 10 seconds.
#   scripts/status.sh [-p PORT] USER@HOST BOOK [SECONDS]
#   scripts/status.sh Ubuntu@154.54.100.124 slomannyj_mech
# With SECONDS 0 it prints once and exits.
set -euo pipefail

port=22
while getopts p: opt; do
  case "$opt" in
    p) port="$OPTARG" ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [[ $# -lt 2 ]]; then
  echo "usage: $0 [-p PORT] USER@HOST BOOK [SECONDS]" >&2
  exit 2
fi
every="${3:-10}"
ssh -t -p "$port" "$1" "cd ~/book-graph && .venv/bin/python -m bookgraph progress $(printf '%q' "$2") -w ${every}"
