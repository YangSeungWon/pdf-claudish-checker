#!/usr/bin/env python3
"""
claudish_check.py — 논문 PDF 본문에서 "Claudish" 문장을 찾아 표시합니다.

Claudish = Claude / Claude Code 특유의 문체. 대조를 만들어 세우고, 중요하다고
예고하고, 구조 은유를 쓰고, 같은 말을 다른 추상 수준으로 되풀이하는 글투.

사용법:
    python3 claudish_check.py paper.pdf
    python3 claudish_check.py paper.pdf --lang en
    python3 claudish_check.py draft.md --json out.json

판정 표는 docs/rules.json 하나뿐이고, 웹 버전도 같은 파일을 읽습니다.
의존성: 없음(표준 라이브러리). PDF 텍스트 추출에만 pdftotext(poppler) 또는
pypdf / pdfminer.six 가 필요합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.environ.get("CLAUDISH_RULES", os.path.join(HERE, "docs", "rules.json"))

LEVEL_ORDER = {"weak": 0, "medium": 1, "strong": 2}


# --------------------------------------------------------------------------
# 0. 규칙 표
# --------------------------------------------------------------------------

def load_rules(path: str = RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    rules["_boiler"] = [re.compile(p, re.IGNORECASE | re.ASCII)
                        for p in rules.get("boilerplate", [])]
    for d in rules["detectors"]:
        # JS 의 \b 는 ASCII 기준이라, 한글이 섞인 줄에서 결과가 갈리지 않도록
        # 파이썬도 ASCII 모드로 맞춘다 (패턴은 모두 영어다)
        flags = re.ASCII | (0 if d.get("caseSensitive") else re.IGNORECASE)
        d["_guard"] = [re.compile(p, re.IGNORECASE | re.ASCII) for p in d.get("guards", [])]
        d["_skip"] = [re.compile(p, flags) for p in d.get("skip", [])]
        # patterns 는 문자열이거나 {re, guards, skip} — 규칙 하나에만 걸리는 예외를
        # 갈래 전체로 번지지 않게 하려고 패턴별로도 받는다
        d["_pat"] = []
        for p in d.get("patterns", []):
            if isinstance(p, str):
                p = {"re": p}
            d["_pat"].append({
                "opt": bool(p.get("opt")),
                "re": re.compile(p["re"], flags),
                "guard": [re.compile(g, re.IGNORECASE | re.ASCII)
                          for g in p.get("guards", [])],
                "skip": [re.compile(g, flags) for g in p.get("skip", [])],
            })
    rules["_stop"] = set(rules["stopwords"])
    return rules


# --------------------------------------------------------------------------
# 1. PDF -> 텍스트
# --------------------------------------------------------------------------

def extract_text(path: str) -> str:
    """PDF 전체 텍스트. 2단 조판을 읽기 순서대로 풀어주는 도구를 우선 사용."""
    if path.lower().endswith((".txt", ".md", ".markdown", ".text")):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    if shutil.which("pdftotext"):
        out = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.decode("utf-8", "replace")

    try:
        import pypdf  # type: ignore

        return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(path).pages)
    except ImportError:
        pass

    try:
        from pdfminer.high_level import extract_text as _pm  # type: ignore

        return _pm(path)
    except ImportError:
        pass

    sys.exit(
        "PDF 텍스트 추출기를 찾을 수 없습니다.\n"
        "  brew install poppler   (권장)\n"
        "  또는  pip install pypdf"
    )


def strip_running_heads(text: str, min_repeat: int = 4) -> str:
    """페이지마다 반복되는 러닝헤드 제거 (문장 한가운데로 끼어든다)."""
    lines = text.split("\n")
    seen: dict[str, int] = {}
    for line in lines:
        k = line.strip()
        if len(k) >= 5:
            seen[k] = seen.get(k, 0) + 1
    out = []
    for l in lines:
        if len(l.strip()) >= 5 and seen.get(l.strip(), 0) >= min_repeat:
            out.append("\f" * l.count("\f"))          # 쪽 경계는 남긴다
        else:
            out.append(l)
    return "\n".join(out)


# --------------------------------------------------------------------------
# 2. 본문만 남기기
# --------------------------------------------------------------------------

# 참고문헌 이후는 사람이 쓴 문장이 아니므로 통째로 버린다
TAIL_RE = re.compile(
    r"^[ \t]*(?:\d+[.\s]*)?(?:REFERENCES|References|Bibliography|BIBLIOGRAPHY|"
    r"Works\s+Cited|참고\s*문헌)[ \t]*$",
    re.MULTILINE,
)

URL_RE = re.compile(r"https?://\S+|\bdoi:\s*\S+|\b10\.\d{4,9}/\S+",
                    re.IGNORECASE | re.ASCII)
CITE_RE = re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")

_DASHES = "‐‑‒–―−"
_SQ = "‘’ʼ"
_DQ = "“”"


def clean(s: str) -> str:
    """표시용 정리. 줄표(—)는 세는 대상이라 남긴다."""
    t = unicodedata.normalize("NFKC", s)
    t = t.replace("ﬀ", "ff").replace("ﬁ", "fi").replace("ﬂ", "fl")
    t = t.replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    for ch in _DASHES:
        t = t.replace(ch, "-")
    for ch in _SQ:
        t = t.replace(ch, "'")
    for ch in _DQ:
        t = t.replace(ch, '"')
    return re.sub(r"\s+", " ", t).strip()


ENDS_RE = re.compile(r"[.!?:,;\"')\]-]$")
NUM_HEAD_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*\.?\s+[A-Z]")


def _skip_line(line: str) -> bool:
    """절 제목·수식·표처럼 문장이 아닌 줄인가.

    2단 조판은 본문 한 줄이 45~55자라 "짧으면 제목" 으로 자를 수 없다.
    끝맺음이 없는 짧은 줄 중에서도 제목처럼 생긴 것만 버린다.
    """
    s = line.strip()
    if len(s) < 3:
        return True
    letters = sum(c.isalpha() for c in s)
    if letters < 3 or letters / len(s) < 0.55:       # 수식·표·숫자 줄
        return True
    if s.isupper():                                   # ABSTRACT, CCS CONCEPTS
        return True
    if len(s) < 75 and not ENDS_RE.search(s):
        if NUM_HEAD_RE.match(s):                      # "3.2 Study Design"
            return True
        words_ = s.split()
        caps = sum(1 for w in words_ if w[:1].isupper())
        if len(words_) <= 9 and caps >= max(2, len(words_) * 0.6):
            return True                               # 제목꼴 (Title Case)
    return False


BARE_NUM_RE = re.compile(r"^[0-9]{1,4}$")
SENT_END_RE = re.compile(r"[.!?][\"')\]]?$")


def prose_paragraphs(text: str, rules: dict) -> list[list[tuple[str, int]]]:
    """PDF 텍스트에서 본문 문단 목록. 각 문단은 페이지 번호가 붙은 줄 묶음.

    빈 줄을 문단 끝으로 그냥 믿을 수 없다. 투고본은 여백에 줄번호가 찍혀
    나오는데, pdftotext 가 그 숫자를 제 줄로 뽑으면서 앞뒤에 빈 줄을 넣기
    때문에 문장 한가운데가 잘린다. 그래서 앞 줄이 문장부호로 끝났을 때만
    빈 줄을 문단 끝으로 본다.
    """
    cut = None
    for m in TAIL_RE.finditer(text):
        cut = m.start()                              # 마지막 References 헤딩
    if cut is not None:
        text = text[:cut]

    paras: list[list[tuple[str, int]]] = []
    cur: list[tuple[str, int]] = []
    page = 1
    pending = False

    def flush() -> None:
        nonlocal cur
        if cur:
            paras.append(cur)
            cur = []

    for raw in text.split("\n"):
        if "\f" in raw:
            page += raw.count("\f")
            raw = raw.replace("\f", " ")
        line = CITE_RE.sub(" ", URL_RE.sub(" ", raw)).strip()
        if not line:
            pending = True
            continue
        if BARE_NUM_RE.match(line):                  # 여백 줄번호 · 쪽번호
            continue
        if _skip_line(line):
            flush()
            pending = False
            continue
        if pending and cur and SENT_END_RE.search(cur[-1][0]):
            flush()
        pending = False
        cur.append((line, page))
    flush()

    return [p for p in paras
            if not any(b.search(" ".join(l for l, _ in p)) for b in rules["_boiler"])]


def join_lines(lines: list[tuple[str, int]]) -> tuple[str, list[tuple[int, int]]]:
    """문단의 줄을 이어 붙이고, 글자 위치 -> 페이지 대응표를 함께 만든다."""
    out = ""
    marks: list[tuple[int, int]] = []
    for text, page in lines:
        if out:
            if out.endswith("-") and text[:1].islower():
                out = out[:-1]                       # 줄바꿈 분철
            else:
                out += " "
        marks.append((len(out), page))
        out += text
    return clean(out), marks


# --------------------------------------------------------------------------
# 3. 문장 나누기  (JS 판 prose.js 와 같은 규칙)
# --------------------------------------------------------------------------

ABBREV = {
    "e.g.", "i.e.", "cf.", "al.", "et.", "etc.", "fig.", "figs.", "eq.", "eqs.",
    "vs.", "dr.", "mr.", "mrs.", "ms.", "prof.", "approx.", "no.", "nos.", "pp.",
    "p.", "ch.", "chap.", "sec.", "sect.", "tab.", "vol.", "ed.", "eds.", "est.",
    "inc.", "ltd.", "st.", "jr.", "sr.", "min.", "max.", "ca.", "resp.", "viz.",
    "ibid.", "vs", "al",
}

_BREAK_RE = re.compile(r"[.!?][\"')\]]*(\s+)")
_TAIL_TOK_RE = re.compile(r"[A-Za-z0-9.]+$")
_NEXT_RE = re.compile(r"^[A-Z0-9\"'(\[]")


def _is_abbrev(head: str) -> bool:
    m = _TAIL_TOK_RE.search(head)
    if not m:
        return False
    tok = m.group(0).lower()
    if tok in ABBREV:
        return True
    if re.fullmatch(r"[a-z]\.", tok):                # 이름 이니셜 "J."
        return True
    if re.fullmatch(r"[0-9]+\.", tok):               # 번호 매기기
        return True
    return False


def split_sentences(para: str) -> list[tuple[int, str]]:
    """(문단 안 시작 위치, 문장) 목록."""
    out: list[tuple[int, str]] = []
    start = 0
    for m in _BREAK_RE.finditer(para):
        end = m.end() - len(m.group(1))
        nxt = para[m.end():]
        if not nxt:
            break
        if _is_abbrev(para[:end]) or not _NEXT_RE.match(nxt):
            continue
        s = para[start:end].strip()
        if s:
            out.append((start, s))
        start = m.end()
    tail = para[start:].strip()
    if tail:
        out.append((start, tail))
    return out


# --------------------------------------------------------------------------
# 4. 판정
# --------------------------------------------------------------------------

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9']*")


def words(s: str) -> list[str]:
    return WORD_RE.findall(s)


LOWER_RE = re.compile(r"[a-z]{2}")


def is_prose(s: str, min_words: int) -> bool:
    """문장으로 셀 만한가. 표 조각·수식 찌꺼기를 걸러낸다."""
    w = words(s)
    if len(w) < min_words:
        return False
    if not LOWER_RE.search(s):                       # 전부 대문자/기호
        return False
    letters = sum(c.isalpha() for c in s)
    return letters / len(s) >= 0.6


def stem(w: str) -> str:
    """아주 가벼운 어간 정리.

    reveal / reveals / revealed / revealing 을 한 낱말로 묶으려는 것뿐이다.
    같은 말 반복(restate)을 재는 데만 쓰므로 정확한 형태소 분석일 필요가 없다.
    """
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 4 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("ly"):
        w = w[:-2]
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]                                   # produce / produced 를 맞춘다
    return w


def content_words(s: str, stop: set) -> set:
    out = set()
    for w in words(s):
        w = w.lower().rstrip("'")
        if len(w) < 3 or w in stop:
            continue
        out.add(stem(w))
    return out


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


CLAUSE_RE = re.compile(r"\s*(?:—|:|;)\s*")


def quote_spans(sent: str) -> list[tuple[int, int]]:
    """큰따옴표로 묶인 구간. 면담 인용문은 글쓴이의 문체가 아니다."""
    out = []
    open_at = None
    for i, ch in enumerate(sent):
        if ch != '"':
            continue
        if open_at is None:
            open_at = i
        else:
            out.append((open_at, i + 1))
            open_at = None
    if open_at is not None:                          # 문장을 넘어가는 인용
        out.append((open_at, len(sent)))
    return out


def scan_sentence(sent: str, rules: dict, strict: bool = True) -> list[dict]:
    """한 문장에서 나온 패턴 히트."""
    hits = []
    quotes = quote_spans(sent) if '"' in sent else []
    for d in rules["detectors"]:
        if d.get("kind") == "structural":
            continue
        if any(g.search(sent) for g in d["_guard"]):
            continue
        in_quote = d.get("notInQuotes") and quotes
        for pat in d["_pat"]:
            if pat["opt"] and not strict:
                continue
            if any(g.search(sent) for g in pat["guard"]):
                continue
            for m in pat["re"].finditer(sent):
                text = m.group(0)
                if any(sk.search(text) for sk in d["_skip"] + pat["skip"]):
                    continue
                if in_quote and any(a <= m.start() < b for a, b in quotes):
                    continue
                hits.append({
                    "id": d["id"], "level": d["level"], "weight": d["weight"],
                    "start": m.start(), "end": m.end(), "text": text,
                })
                break                                # 같은 패턴은 문장당 한 번
    return hits


def drop_repeated_terms(sents: list[dict], rules: dict) -> list[dict]:
    """여러 문장에 되풀이해 나오는 말은 그 글의 용어로 보고 문체로 세지 않는다.

    논문이 스스로 정의한 이름("Cue-First" 같은 조건 이름)을 붙여 만든 명사 덩어리라고
    지적하면 같은 지적이 수십 번 나온다. 대신 무엇을 뺐는지는 밝힌다.
    """
    limits = {d["id"]: d["repeatLimit"] for d in rules["detectors"] if d.get("repeatLimit")}
    if not limits:
        return []
    count: dict[tuple[str, str], int] = {}
    for s in sents:
        for key in {(h["id"], h["text"].lower()) for h in s["hits"] if h["id"] in limits}:
            count[key] = count.get(key, 0) + 1

    dropped = {k for k, n in count.items() if n > limits[k[0]]}
    if not dropped:
        return []
    for s in sents:
        s["hits"] = [h for h in s["hits"] if (h["id"], h["text"].lower()) not in dropped]
    return sorted(
        ({"id": i, "text": t, "count": count[(i, t)]} for i, t in dropped),
        key=lambda x: (-x["count"], x["id"], x["text"]),
    )


def structural_hits(sents: list[dict], rules: dict) -> None:
    """줄표 남발과 같은 말 반복. 문장 하나만 봐서는 알 수 없는 것들."""
    opt = rules["options"]
    by_id = {d["id"]: d for d in rules["detectors"]}

    for s in sents:
        n = s["text"].count("—")
        if n >= opt["emdashPerSentence"]:
            d = by_id["emdash"]
            i = s["text"].find("—")
            s["hits"].append({
                "id": "emdash", "level": d["level"], "weight": d["weight"],
                "start": i, "end": i + 1, "text": "— x%d" % n,
            })

        # 한 문장 안에서 ':' '—' ';' 앞뒤가 같은 말인 경우
        parts = [p for p in CLAUSE_RE.split(s["text"]) if p]
        if len(parts) >= 2:
            for a, b in zip(parts, parts[1:]):
                ca, cb = content_words(a, rules["_stop"]), content_words(b, rules["_stop"])
                if (len(ca) >= opt["clauseMinContent"] and len(cb) >= opt["clauseMinContent"]
                        and jaccard(ca, cb) >= opt["clauseJaccard"]):
                    d = by_id["restate"]
                    s["hits"].append({
                        "id": "restate", "level": d["level"], "weight": d["weight"],
                        "start": 0, "end": len(s["text"]), "text": "",
                        "kind": "clause",
                    })
                    break

    # 긴 문장 뒤에 붙인 짧은 한 마디, 같은 첫머리의 되풀이, 한 문장짜리 문단.
    # 셋 다 앞뒤를 봐야 알 수 있어서 여기서 함께 잰다.
    d = by_id["beat"]
    openers = set(opt["beatOpeners"])
    def add_beat(s: dict, kind: str, prev: int | None, text: str = "") -> None:
        s["hits"].append({
            "id": "beat", "level": d["level"], "weight": d["weight"],
            "start": 0, "end": len(text) if text else len(s["text"]),
            "text": text, "kind": kind, **({"prev": prev} if prev is not None else {}),
        })

    for i in range(1, len(sents)):
        b = sents[i]
        wb = words(b["text"])
        a = sents[i - 1]
        if a["para"] != b["para"]:
            continue
        # 판정 한 마디: 짧고, 앞이 길고, 새로 말하는 내용이 거의 없다
        if (len(wb) <= opt["beatShortWords"]
                and len(words(a["text"])) >= opt["beatLongWords"]
                and wb[0].lower() in openers
                and len(content_words(b["text"], rules["_stop"])) <= opt["beatMaxContent"]):
            add_beat(b, "short", a["i"])
            continue
        # 같은 첫머리가 세 문장 이어질 때만 연출로 본다 (두 번은 자연스럽다)
        n = opt["anaphoraWords"]
        run = opt["anaphoraRun"]
        if i + 1 >= run and len(wb) >= n:
            head = [w.lower() for w in wb[:n]]
            same = all(
                sents[j]["para"] == b["para"]
                and len(words(sents[j]["text"])) >= n
                and [w.lower() for w in words(sents[j]["text"])[:n]] == head
                for j in range(i - run + 1, i)
            )
            if same:
                add_beat(b, "anaphora", a["i"], " ".join(wb[:n]))

    # 이웃한 두 문장이 같은 말인 경우
    for i in range(1, len(sents)):
        a, b = sents[i - 1], sents[i]
        if a["para"] != b["para"]:
            continue
        ca = content_words(a["text"], rules["_stop"])
        cb = content_words(b["text"], rules["_stop"])
        if (len(ca) >= opt["restateMinContent"] and len(cb) >= opt["restateMinContent"]
                and jaccard(ca, cb) >= opt["restateJaccard"]):
            d = by_id["restate"]
            if not any(h["id"] == "restate" for h in b["hits"]):
                b["hits"].append({
                    "id": "restate", "level": d["level"], "weight": d["weight"],
                    "start": 0, "end": len(b["text"]), "text": "",
                    "kind": "neighbor", "prev": a["i"],
                })


def analyze(text: str, rules: dict, strict: bool = True) -> dict:
    opt = rules["options"]
    sents: list[dict] = []
    for pi, lines in enumerate(prose_paragraphs(text, rules)):
        para, marks = join_lines(lines)
        for off, s in split_sentences(para):
            if not is_prose(s, opt["minSentenceWords"]):
                continue
            page = marks[0][1]
            for pos, pg in marks:
                if pos <= off:
                    page = pg
                else:
                    break
            sents.append({
                "i": len(sents), "para": pi, "page": page, "text": s, "hits": [],
            })

    for s in sents:
        s["hits"] = scan_sentence(s["text"], rules, strict)
    terms = drop_repeated_terms(sents, rules)
    structural_hits(sents, rules)

    n_words = sum(len(words(s["text"])) for s in sents)
    flagged = [s for s in sents if s["hits"]]
    weight = sum(h["weight"] for s in flagged for h in s["hits"])
    score = (weight / n_words * 1000) if n_words else 0.0

    band = rules["bands"][-1]["id"]
    for b in rules["bands"]:
        if b["max"] is not None and score < b["max"]:
            band = b["id"]
            break

    counts: dict[str, int] = {}
    for s in flagged:
        for h in s["hits"]:
            counts[h["id"]] = counts.get(h["id"], 0) + 1

    return {
        "sentences": sents, "flagged": flagged, "words": n_words,
        "score": round(score, 2), "band": band, "counts": counts, "terms": terms,
    }


# --------------------------------------------------------------------------
# 5. 출력
# --------------------------------------------------------------------------

class C:
    def __init__(self, on: bool):
        self.R = "\033[31m" if on else ""
        self.Y = "\033[33m" if on else ""
        self.G = "\033[32m" if on else ""
        self.B = "\033[1m" if on else ""
        self.D = "\033[2m" if on else ""
        self.U = "\033[4m" if on else ""
        self.X = "\033[0m" if on else ""


MSG = {
    "ko": {
        "body": "본문", "sent": "문장", "word": "단어", "flagged": "지적",
        "score": "claudish 지수", "per": "/1000단어",
        "band": {"clean": "깨끗함", "light": "옅음", "some": "눈에 띔", "heavy": "짙음"},
        "byDetector": "갈래별", "none": "짚을 문장이 없습니다.",
        "restateNeighbor": "앞 문장과 같은 말",
        "restateClause": "문장 안에서 같은 말을 되풀이",
        "beat": {"short": "긴 문장 뒤에 붙인 한 마디",
                 "anaphora": "같은 첫머리로 세 문장째"},
        "more": "…그 밖에 %d개 (전부 보려면 --all)",
        "noProse": "본문 문장을 찾지 못했습니다. --dump-text 로 뽑아낸 본문을 확인해 보세요.",
        "level": {"strong": "강함", "medium": "중간", "weak": "약함"},
        "page": "쪽",
        "terms": "이 글이 쓰는 용어로 보고 뺀 것", "andMore": "외 %d개",
    },
    "en": {
        "body": "body", "sent": "sentences", "word": "words", "flagged": "flagged",
        "score": "claudish score", "per": "/1000 words",
        "band": {"clean": "clean", "light": "light", "some": "noticeable", "heavy": "heavy"},
        "byDetector": "By pattern", "none": "Nothing to flag.",
        "restateNeighbor": "repeats the previous sentence",
        "restateClause": "repeats itself across the dash or colon",
        "beat": {"short": "a verdict line dropped after a long sentence",
                 "anaphora": "the third sentence in a row opening the same way"},
        "more": "…and %d more sentences (--all to see them)",
        "noProse": "No body sentences found. Check --dump-text.",
        "level": {"strong": "strong", "medium": "medium", "weak": "weak"},
        "page": "p.",
        "terms": "excluded as the paper's own terminology", "andMore": "and %d more",
    },
}

LEVEL_COLOR = {"strong": "R", "medium": "Y", "weak": "D"}


def underline(sent: str, hits: list[dict], c: C, width: int = 400) -> str:
    """히트 구간에 밑줄. 겹치는 구간은 하나로 합친다."""
    spans = sorted((h["start"], h["end"]) for h in hits
                   if h["end"] > h["start"] and h.get("kind") is None)
    merged: list[list[int]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out, pos = "", 0
    for a, b in merged:
        out += sent[pos:a] + c.U + c.B + sent[a:b] + c.X
        pos = b
    out += sent[pos:]
    if len(sent) > width:
        out = out[: width + (len(out) - len(sent))] + "…"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="논문 PDF 본문에서 Claude가 쓴 것 같은 문장을 찾아 표시합니다."
    )
    ap.add_argument("path", help="검사할 PDF (또는 .txt/.md)")
    ap.add_argument("--lang", choices=["ko", "en"], default="ko")
    ap.add_argument("--min-level", choices=["weak", "medium", "strong"], default="weak",
                    help="이 등급 이상만 (기본 weak = 전부)")
    ap.add_argument("--only", metavar="ID", help="갈래 하나만 볼 때 (쉼표로 여러 개)")
    ap.add_argument("--all", action="store_true", help="짚은 문장을 전부 출력")
    ap.add_argument("--limit", type=int, default=40, help="출력할 문장 수 (기본 40)")
    ap.add_argument("--json", metavar="FILE", help="결과를 JSON으로 저장")
    ap.add_argument("--dump-text", metavar="FILE", help="뽑아낸 본문 문장을 파일로 저장 (파싱이 이상할 때)")
    ap.add_argument("--rules", metavar="FILE", default=RULES_PATH, help="판정 표 경로")
    ap.add_argument("--fail-on", choices=["never", "strong", "medium", "weak"],
                    default="strong", help="이 등급이 나오면 종료 코드 1 (기본 strong)")
    ap.add_argument("--loose", action="store_true",
                    help="provenance·canonical·drift·X-level·protocol 처럼 정식 "
                         "용어로도 흔히 쓰이는 낱말은 넘어간다")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"파일을 찾을 수 없습니다: {args.path}", file=sys.stderr)
        return 2

    c = C(sys.stdout.isatty() and not args.no_color)
    m = MSG[args.lang]
    rules = load_rules(args.rules)
    label = {d["id"]: d["label"][args.lang] for d in rules["detectors"]}
    advice = {d["id"]: d["advice"][args.lang] for d in rules["detectors"]}

    text = strip_running_heads(extract_text(args.path))
    rep = analyze(text, rules, not args.loose)

    if args.dump_text:
        with open(args.dump_text, "w", encoding="utf-8") as f:
            for s in rep["sentences"]:
                f.write(f"[{s['page']}/{s['para']}] {s['text']}\n")

    if not rep["sentences"]:
        print(m["noProse"], file=sys.stderr)
        return 2

    keep = set(args.only.split(",")) if args.only else None
    floor = LEVEL_ORDER[args.min_level]

    shown = []
    for s in rep["flagged"]:
        hits = [h for h in s["hits"]
                if LEVEL_ORDER[h["level"]] >= floor and (keep is None or h["id"] in keep)]
        if hits:
            shown.append({**s, "hits": hits})

    print(f"{c.B}{os.path.basename(args.path)}{c.X}  "
          f"{m['body']} {len(rep['sentences']):,} {m['sent']} · {rep['words']:,} {m['word']} · "
          f"{m['flagged']} {len(shown):,}")

    sc = rep["score"]
    band = m["band"][rep["band"]]
    col = c.G if rep["band"] in ("clean", "light") else (c.Y if rep["band"] == "some" else c.R)
    print(f"{m['score']} {col}{c.B}{sc}{c.X}{m['per']}  ({col}{band}{c.X})")

    if rep["counts"]:
        print(f"\n{c.B}{m['byDetector']}{c.X}")
        order = {d["id"]: i for i, d in enumerate(rules["detectors"])}
        for did, n in sorted(rep["counts"].items(), key=lambda kv: order[kv[0]]):
            if keep is not None and did not in keep:
                continue
            d = next(x for x in rules["detectors"] if x["id"] == did)
            if LEVEL_ORDER[d["level"]] < floor:
                continue
            lc = getattr(c, LEVEL_COLOR[d["level"]])
            print(f"  {lc}{n:>4}{c.X}  {label[did]} {c.D}[{did} · {m['level'][d['level']]}]{c.X}")

    if rep["terms"]:
        listed = ", ".join(f"{t['text']} ({t['count']})" for t in rep["terms"][:8])
        extra = len(rep["terms"]) - 8
        print(f"\n{c.D}{m['terms']}: {listed}"
              + (f" {m['andMore'] % extra}" if extra > 0 else "") + c.X)

    if not shown:
        print(f"\n{c.G}{m['none']}{c.X}")
    else:
        cap = len(shown) if args.all else min(len(shown), args.limit)
        for s in shown[:cap]:
            worst = max(s["hits"], key=lambda h: LEVEL_ORDER[h["level"]])
            lc = getattr(c, LEVEL_COLOR[worst["level"]])
            mark = {"strong": "✗", "medium": "⚠", "weak": "·"}[worst["level"]]
            print(f"\n{lc}{mark}{c.X} {c.D}{m['page']}{s['page']}{c.X} "
                  f"{underline(s['text'], s['hits'], c)}")
            for h in sorted(s["hits"], key=lambda h: -LEVEL_ORDER[h["level"]]):
                hc = getattr(c, LEVEL_COLOR[h["level"]])
                if h["id"] == "restate":
                    what = m["restateClause"] if h.get("kind") == "clause" else m["restateNeighbor"]
                elif h["id"] == "beat":
                    what = m["beat"][h.get("kind", "short")]
                else:
                    what = f'"{h["text"]}"'
                print(f"    {hc}•{c.X} {label[h['id']]} — {what}")
                print(f"      {c.D}{advice[h['id']]}{c.X}")
        if cap < len(shown):
            print(f"\n{c.D}{m['more'] % (len(shown) - cap)}{c.X}")

    if args.json:
        payload = {
            "file": os.path.abspath(args.path),
            "words": rep["words"], "sentences": len(rep["sentences"]),
            "score": rep["score"], "band": rep["band"], "counts": rep["counts"],
            "excluded_terms": rep["terms"],
            "flagged": [
                {"page": s["page"], "text": s["text"],
                 "hits": [{k: v for k, v in h.items() if k != "weight"} for h in s["hits"]]}
                for s in shown
            ],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n{c.D}JSON: {args.json}{c.X}")

    if args.fail_on == "never":
        return 0
    bar = LEVEL_ORDER[args.fail_on]
    return 1 if any(LEVEL_ORDER[h["level"]] >= bar for s in shown for h in s["hits"]) else 0


if __name__ == "__main__":
    sys.exit(main())
