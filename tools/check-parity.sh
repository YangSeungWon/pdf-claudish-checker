#!/bin/sh
# CLI 와 웹이 같은 텍스트에서 같은 판정을 내는지 확인한다.
#
#   tools/check-parity.sh paper.pdf draft.md ...
#
# PDF 는 pdftotext 로 한 번 풀어서 두 구현에 똑같이 넣는다. 추출기(pdftotext /
# pdf.js)가 다른 것은 여기서 따지지 않는다 — 판정 로직만 본다.
set -e
STRICT=""
if [ "$1" = "--loose" ]; then STRICT="--loose"; shift; fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
root=$(cd "$(dirname "$0")/.." && pwd)
fail=0

for f in "$@"; do
  case "$f" in
    *.pdf) pdftotext -enc UTF-8 "$f" "$tmp/in.txt" ;;
    *)     cp "$f" "$tmp/in.txt" ;;
  esac
  python3 "$root/tools/parity.py" "$tmp/in.txt" $STRICT > "$tmp/cli.json"
  node "$root/tools/parity.mjs" "$tmp/in.txt" $STRICT > "$tmp/web.json"
  if diff -q "$tmp/cli.json" "$tmp/web.json" > /dev/null; then
    echo "ok   $(basename "$f")"
  else
    echo "DIFF $(basename "$f")"
    diff "$tmp/cli.json" "$tmp/web.json" | head -20
    fail=1
  fi
done
exit $fail
