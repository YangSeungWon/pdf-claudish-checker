#!/usr/bin/env python3
"""규칙 자가 점검.

    python3 tools/selftest.py

세 가지를 확인합니다.

1. 갈래마다 예문이 하나라도 있는가 — `assistant` 갈래가 통째로 시험된 적이
   없어서 고장난 패턴을 한동안 못 봤던 적이 있습니다.
2. 그 예문을 실제로 잡는가.
3. 잡으면 안 되는 문장(정상적인 연구 글)을 잡지 않는가.

종료 코드: 실패가 있으면 1.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import claudish_check as cc  # noqa: E402

# 갈래 -> 그 갈래가 잡아야 하는 문장들
HIT: dict[str, list[str]] = {
    "assistant": [
        "Let me be direct about what this study can and cannot show.",
        "Certainly, the effect could also be explained by novelty.",
        "As an AI, I cannot verify the provenance of these responses.",
        "Feel free to skip the appendix if you only want the results.",
        "Here's a quick rundown of the three conditions for you.",
        "Let me know if you would like the full transcripts.",
    ],
    "validation": [
        "You're absolutely right about the ordering.",
        "That is a great question, and it deserves a longer answer.",
        "To be honest, the sample is too small for that claim.",
        "One honest caveat is that we never measured retention.",
    ],
    "staged": [
        "The key distinction is between showing and asking.",
        "It's worth noting that the effect reverses in the second week.",
        "Importantly, the cue never names the task directly.",
        "This is where the associative prompt comes in.",
        "At the heart of the design is a refusal to instruct.",
    ],
    "aphorism": [
        "That is the boundary.",
        "That distinction matters.",
        "Nothing more, nothing less.",
    ],
    "contrast": [
        "The goal was not just to describe a phenomenon, but to explain it.",
        "The question is not whether the cue is noticed but whether it is acted on.",
        "The design is not so much a reminder as an invitation.",
        "It would be a mistake to read this as a claim about accuracy.",
    ],
    "orient": [
        "In other words, the archive is an intervention.",
        "Put differently, the person speaks before the system does.",
        "That is to say, the cue is recognized rather than read.",
        "Essentially, the system waits for the user to notice.",
    ],
    "metaphor": [
        "The ordering is load-bearing for the whole design.",
        "This work sits at the intersection of memory research and feed design.",
        "The design threads the needle between visibility and intrusion.",
        "We treat the transcript as the canonical record.",
    ],
    "compound": [
        "The release path is approval-gated by design.",
        "We used a memory-backed index for the study.",
    ],
    "abstract": [
        "The timestamp provides verified evidence of cache staleness.",
        "Passing tests is a mandatory requirement.",
        "Merge authority is restricted to the owner role.",
    ],
    "research": [
        "This is the frontier of interactive remembering.",
        "The engineering here is non-trivial.",
        "We deployed the system in the wild for five weeks.",
        "The finding survives scrutiny under the stricter test.",
    ],
    "rhythm": [
        "And that is exactly the problem.",
        "Three constraints shaped the design: recognizability, deniability, and restraint.",
    ],
    "triad": [
        "The style is rhetorically polished, structurally metaphorical, and relentlessly abstract.",
    ],
    "emdash": [
        "The ordering — not the model — is what matters — and it always was.",
    ],
    "restate": [
        "The interface reveals a photograph after the participant produces a matching "
        "description. A photograph is revealed by the interface after the participant "
        "has produced a description that matches.",
    ],
    "beat": [
        "Participants noticed the cue, recognized the interrupted task, and then went "
        "back to the feed without acting on it. That was enough.",
    ],
}

# 어떤 갈래에도 걸리면 안 되는 정상적인 연구 문장
MISS: list[str] = [
    "We recruited 24 participants through university mailing lists.",
    "Each session lasted approximately 40 minutes and was audio recorded.",
    "Two authors independently coded the transcripts and resolved disagreements.",
    "Figure 3 shows the distribution of responses across the three conditions.",
    "We report means and standard deviations for each measure.",
    "The difference was not statistically significant.",
    "Participants completed a questionnaire before and after each task.",
    "This section describes the system architecture and its components.",
]


def main() -> int:
    rules = cc.load_rules()
    ids = [d["id"] for d in rules["detectors"]]

    def fired(text: str) -> set:
        return {h["id"] for s in cc.analyze(text, rules)["sentences"] for h in s["hits"]}

    fails = []

    missing = [i for i in ids if i not in HIT]
    for i in missing:
        fails.append(f"갈래 '{i}' 에 예문이 없습니다 (tools/selftest.py 에 추가하세요)")

    n_hit = 0
    for det, examples in HIT.items():
        for s in examples:
            n_hit += 1
            if det not in fired(s):
                fails.append(f"[{det}] 못 잡음: {s[:70]}")

    for s in MISS:
        got = fired(s)
        if got:
            fails.append(f"[오탐] {sorted(got)} ← {s[:70]}")

    print(f"갈래 {len(ids)}개 · 예문 {n_hit}개 · 정상문 {len(MISS)}개")
    if fails:
        print(f"\n실패 {len(fails)}건")
        for f in fails:
            print("  " + f)
        return 1
    print("전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
