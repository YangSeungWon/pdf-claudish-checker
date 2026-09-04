#!/usr/bin/env python3
"""CLI 판정 결과를 parity.mjs 와 같은 모양의 JSON 으로 뱉는다.

    python3 tools/parity.py body.txt > cli.json
    node tools/parity.mjs body.txt > web.json
    diff cli.json web.json

같은 텍스트를 넣었을 때 두 구현이 한 글자도 다르지 않아야 한다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import claudish_check as cc  # noqa: E402


def main() -> int:
    rules = cc.load_rules()
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    rep = cc.analyze(text, rules, "--loose" not in sys.argv)
    json.dump({
        "words": rep["words"],
        "sentences": len(rep["sentences"]),
        "score": rep["score"],
        "band": rep["band"],
        "counts": rep["counts"],
        "terms": rep["terms"],
        "flagged": [
            {"page": s["page"], "text": s["text"],
             "hits": [{"id": h["id"], "start": h["start"], "end": h["end"],
                       "text": h["text"], "kind": h.get("kind")} for h in s["hits"]]}
            for s in rep["flagged"]
        ],
    }, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
