# pdf-claudish-checker

논문 초고에서 **Claude 냄새 나는 문장**을 찾아 표시합니다.

- **웹**: <https://claudish.ysw.kr> — 서버 없이 브라우저에서만 동작
- **CLI**: `python3 claudish_check.py paper.pdf`

둘은 같은 판정 표(`docs/rules.json`)와 같은 판정 코드를 씁니다.
같은 텍스트를 넣으면 결과가 완전히 일치하는지 `tools/check-parity.sh` 로 확인합니다.

## Claudish 란

Claude / Claude Code 가 쓰는 글의 버릇입니다. 틀린 쪽을 세워 두고 부정하고,
중요하다고 예고한 다음 말하고, 구조를 은유로 부르고, 같은 말을 추상 수준만
바꿔 되풀이합니다. 문장 하나하나는 멀쩡한데 모아 놓으면 사람이 쓴 것 같지
않습니다.

이 도구는 **문체만** 봅니다. 내용이 맞는지, 사람이 썼는지는 판단하지 않습니다.
지적된 문장이 전부 고쳐야 할 문장인 것도 아닙니다 — 다시 읽어 볼 자리를
짚어 줄 뿐입니다.

## 무엇을 잡아주나

| 갈래 | 등급 | 예 |
|---|---|---|
| `assistant` | 강함 | `As an AI...`, `Let me be direct`, `Feel free to` — 대화용 문장이 그대로 남은 것 |
| `validation` | 강함 | `You're absolutely right`, `to be honest`, `the honest answer` |
| `staged` | 강함 | `The key distinction is...`, `It's worth noting`, `Notably,`, `the verdict` |
| `aphorism` | 강함 | `That distinction matters.`, `That's the point.`, `Nothing more, nothing less.` |
| `contrast` | 중간 | `not just X but Y`, `X isn't A — it's B`, `..., not Y.` |
| `orient` | 중간 | `In other words`, `Put differently`, `At its core`, `That said` |
| `metaphor` | 중간 | `load-bearing`, `guardrails`, `north star`, `the happy path`, `surfaced the issue` |
| `compound` | 중간 | `approval-gated`, `memory-backed`, `attack-adjacent` 같은 하이픈 명사 덩어리 |
| `abstract` | 중간 | `a fact-preservation pass`, `mandatory requirement`, `authority is restricted to` |
| `research` | 약함 | `the frontier`, `in the wild`, `at scale`, `non-trivial`, `modulo` |
| `rhythm` | 중간 | `And that is exactly the problem.` — 접속사로 시작하는 단문 |
| `beat` | 약함 | 긴 문장 뒤의 한 마디, 같은 첫머리로 세 문장째 |
| `triad` | 약함 | `polished, contrast-heavy, and metaphorical` — 셋씩 늘어놓기 |
| `emdash` | 약함 | 한 문장에 줄표(—)가 둘 이상 |
| `restate` | 중간 | 앞 문장과 같은 말이거나, 콜론·줄표 앞뒤가 같은 말 |

등급은 **얼마나 확실한 신호인가**이지 얼마나 나쁜가가 아닙니다.
`강함`은 손으로 쓴 논문에 거의 안 나오는 표현, `약함`은 그것만으로는 단서일 뿐인 것입니다.

`assistant`·`validation`·`orient` 는 **큰따옴표 안에서 나오면 세지 않습니다.**
면담 인용문에는 `to be honest` 같은 말이 자연스럽게 나오는데, 그건 글쓴이의 문체가 아닙니다.

## claudish 지수

지적된 항목의 가중치 합을 본문 1000단어로 나눈 값입니다.

| 지수 | 판정 |
|---|---|
| 2 미만 | 깨끗함 |
| 2–5 | 옅음 |
| 5–12 | 눈에 띔 |
| 12 이상 | 짙음 |

기준은 실측으로 잡았습니다. 사람이 쓴 CHI 논문 두 편이 **2.90 / 1.59**,
Claude가 쓴 것처럼 만든 문단이 **133** 이었습니다.
(`--loose`로 좁게 보면 각각 1.28 / 1.45)

## CLI

```
python3 claudish_check.py paper.pdf
```

`.txt` `.md` 도 그대로 받습니다 (초고를 PDF로 굽기 전에 확인할 때).

### 옵션

```
--lang ko|en        출력 언어 (기본 ko)
--all               지적된 문장을 전부 출력 (기본은 40개)
--limit N           출력할 문장 수
--min-level L       weak|medium|strong — 이 등급 이상만
--only ID           갈래 하나만 (쉼표로 여러 개): --only staged,aphorism
--json FILE         결과를 JSON으로 저장
--dump-text FILE    추출된 본문 문장 저장 (파싱이 이상할 때)
--rules FILE        다른 판정 표 사용 (기본 docs/rules.json)
--loose             정식 용어로도 흔한 낱말(provenance·canonical·X-level 등)은 빼고
--fail-on L         이 등급이 나오면 종료 코드 1 (기본 strong, never 로 끔)
--no-color
```

종료 코드: `--fail-on` 등급이 하나라도 나오면 `1`, 없으면 `0`, 파일·추출 문제는 `2`.

### 요구사항

표준 라이브러리만 씁니다. 텍스트 추출만 외부 도구가 필요합니다.

```
brew install poppler      # pdftotext — 권장
# 또는
pip install pypdf         # 폴백
```

## 웹 버전 (`docs/`)

빌드 단계가 없는 정적 페이지입니다.

- PDF는 **브라우저 밖으로 나가지 않습니다.** 네트워크로 나가는 요청이 아예 없습니다
  (판정에 외부 서비스를 쓰지 않습니다).
- 언어는 브라우저 설정을 따라 영어/한국어가 잡히고 우상단에서 바꿀 수 있습니다.
- 요약의 갈래(칩)를 누르면 그 갈래만 걸러 봅니다.
- `restate`(앞 문장과 같은 말)로 걸린 문장은 **앞 문장을 같이 보여줍니다.**
  그래야 정말 같은 말인지 눈으로 판단할 수 있습니다.
- `pdf.js`는 `docs/vendor/pdfjs/`에 포함돼 있어 CDN 의존성이 없습니다.

로컬 확인:

```
cd docs && python3 -m http.server 8000
```

`rules.json`을 `fetch`로 읽으므로 `file://`이 아니라 http로 띄워야 합니다.

### 배포

1. 저장소 Settings → Pages → Source: `main` 브랜치의 `/docs` 폴더
2. `docs/CNAME`에 `claudish.ysw.kr`이 들어 있습니다.
   DNS에 `claudish` → `<사용자명>.github.io` **CNAME 레코드**를 추가하세요.
3. Pages 설정에서 *Enforce HTTPS* 체크

## 판정 표 (`docs/rules.json`)

갈래·정규식·조언 문구가 전부 이 파일 하나에 있습니다. CLI와 웹이 같은 파일을 읽습니다.

```json
{
  "id": "orient",
  "level": "medium",
  "weight": 2,
  "label": { "en": "Redundant orientation", "ko": "군더더기 안내" },
  "advice": { "en": "...", "ko": "..." },
  "patterns": ["\\bin other words\\b", { "re": "...", "guards": ["..."] }]
}
```

- `patterns` — 문자열이거나 `{re, guards, skip}`.
  `guards`는 **문장 어딘가에** 걸리면 그 패턴을 통째로 건너뛰고,
  `skip`은 **잡힌 문자열 자체**가 걸리면 그 건만 버립니다.
- `guards`/`skip`을 갈래 전체에 걸 수도 있지만, 규칙 하나에만 해당하는 예외는
  패턴 쪽에 두세요. 갈래 전체에 걸면 엉뚱한 규칙까지 같이 죽습니다.
- `caseSensitive: true` — 대소문자 구분 (`compound`가 씁니다)
- `repeatLimit: N` — 같은 문자열이 N개 문장을 넘겨 나오면 그 글의 용어로 보고 제외
- `notInQuotes: true` — 큰따옴표 안에서 나온 것은 세지 않음
- `kind: "structural"` — 정규식이 아니라 코드로 판정 (`emdash`, `restate`, `beat`)
- 패턴에 `opt: true` — 정식 용어로도 흔한 낱말. 기본은 켜짐, `--loose`로 끔

정규식은 **파이썬 `re`와 JS `RegExp`가 똑같이 해석하는 문법만** 씁니다.
뒤돌아보기(lookbehind)와 `\w` `\d`는 쓰지 않고, 매칭은 양쪽 다 ASCII 모드로 돕니다
(파이썬은 `re.ASCII`). JS의 `\b`가 ASCII 기준이라 맞춰 둔 것으로,
`cue-first에서`처럼 한글이 바로 붙은 자리에서 결과가 갈리는 것을 막습니다.

## 얼마나 잡나

두 벌로 재고 있습니다.

**1. 스펙 목록 79/81 (98%)** — 원래 규칙 문서에 이름이 적힌 표현 81개.

| 스펙 항목군 | 커버 |
|---|---|
| contrastive framing (`not X but Y`, `X, not Y`, `less X than Y`) | 4/4 |
| staged emphasis (`the key distinction` … `the smoking gun`) | 7/7 |
| redundant orientation (`in one sentence`, `put differently` …) | 4/4 |
| aphoristic endings (`that distinction matters` …) | 3/3 |
| validation / candor (`you're absolutely right`, `fair hit` …) | 4/4 |
| structural metaphors (`X-gated` … `drift`) | 19/19 |
| technical compounds (`X-gated` … `X-boundary`) | 11/11 |
| over-formal vocabulary (`frontier` … `implicates`) | 19/19 |
| lowest level of abstraction (Prefer 예시) | 5/5 |
| rule of three · em dash | 2/2 |
| semantic compression (restatement) | 1/3 |
| **합계** | **79/81 (98%)** |

남은 것은 `restate` 둘입니다.

- **낱말을 완전히 바꿔 되풀이하는 경우** — "The archive shapes what is remembered.
  Stored records condition subsequent recollection." 낱말 겹침으로 재기 때문에
  원리상 못 잡습니다.
- **아주 짧은 절 반복** — 양쪽 절의 내용어가 2개 미만이면 유사도가 의미 없어 셈에서 뺍니다.

`preserve logical scope`(범위를 넓히지 말 것)와 `perform a visible rewrite`는
고쳐 쓸 때 지킬 규칙이지 찾아낼 문체가 아니라서 검사 대상이 아닙니다.

## 넓게 볼지 좁게 볼지

`provenance` `canonical` `drift` `stale` `X-level` `protocol` `confirmatory`
`lower bound` `matched` 처럼 **정식 기술 용어로도 흔히 쓰이는 낱말**은
`rules.json`에서 `opt: true`로 표시돼 있습니다. **기본은 켜져 있습니다** —
일단 잡아 놓고 사람이 판단하는 쪽이 낫기 때문입니다.

끄려면 CLI는 `--loose`, 웹은 `정식 용어까지` 체크를 해제하면 됩니다.

여전히 안 잡는 것도 있습니다.

- **`-aware` `-agnostic` `-driven` `-only` `-facing`.** 굳어진 표현이 너무 많습니다.
- **`scaffolding` `tension between` `trajectory`(운동 맥락).** 학습과학·HCI의 정식 용어입니다.
- **논문이 스스로 정의한 이름.** `Cue-First`, `Delay-First` 같은 조건 이름처럼 대문자로 시작하거나
  문서 전체에서 3개 문장을 넘겨 되풀이되는 하이픈 합성어는 그 글의 용어로 봅니다.
  무엇을 뺐는지는 결과에 그대로 적습니다 (`그 글의 용어로 보아 제외: ...`).

## 본문만 골라내기

문체는 본문에서만 셉니다.

- **참고문헌 이후**는 통째로 버립니다 (`References` 헤딩 중 마지막 것 기준).
- **페이지마다 반복되는 머리글/바닥글**을 지웁니다. 쪽 경계(`\f`)는 남겨서
  지적한 문장의 쪽수가 어긋나지 않게 합니다.
- **ACM 저작권 문구, `CCS Concepts`, `ACM Reference Format`** 등 정해진 문구가 든
  문단은 글쓴이가 쓴 것이 아니므로 뺍니다 (`boilerplate` 목록).
- **절 제목·표·수식 줄**을 거릅니다. 2단 조판은 본문 한 줄이 45~55자라
  "짧으면 제목"으로 자를 수 없어서, 끝맺음이 없는 짧은 줄 중 제목처럼 생긴 것만
  버립니다.
- URL과 `[12, 13]` 형태의 인용 표기는 문장에서 빼고 셉니다.

### 문단 경계

빈 줄을 문단 끝으로 그냥 믿을 수 없습니다. ACM 투고본은 여백에 줄번호가 찍혀
나오는데, `pdftotext`가 그 숫자를 제 줄로 뽑으면서 앞뒤에 빈 줄을 넣기 때문에
문장 한가운데가 잘립니다. 그래서 **앞 줄이 문장부호로 끝났을 때만** 빈 줄을
문단 끝으로 봅니다.

웹 버전은 `pdf.js`에서 좌표를 직접 받으므로 이 추측이 필요 없습니다.
줄 간격이 평소보다 벌어졌거나 왼쪽이 들여쓰기된 줄을 문단 시작으로 보고,
여백 줄번호는 세로로 늘어선 숫자 열로 알아보고 지웁니다.

문단 경계는 `restate`(앞 문장과 같은 말) 판정에만 쓰입니다. 문단을 잘못 이어 붙여도
문장 나누기는 그대로이고, 비교 대상이 한 쌍 늘어날 뿐입니다.

## CLI와 웹이 같은지 확인

```
tools/check-parity.sh paper.pdf draft.md
```

PDF는 `pdftotext`로 한 번 풀어서 두 구현에 똑같이 넣고, 문장 목록·지적 위치·지수까지
JSON으로 뽑아 `diff` 합니다. 실측한 네 건(사람이 쓴 CHI 논문 2편, 만든 예시 2건)에서
한 글자도 다르지 않습니다.

**추출기 차이는 여기서 따지지 않습니다.** `pdftotext`와 `pdf.js`는 같은 PDF에서도
줄을 조금 다르게 뽑기 때문에 문장 수와 지수가 몇 % 다를 수 있습니다
(실측: 같은 논문에서 CLI 527문장, 웹 513문장). 이 스크립트가 보장하는 것은
**같은 텍스트를 넣었을 때 판정이 같다**는 것입니다. `--loose`를 앞에 붙이면 그 모드로 확인합니다.

## 한계

- 영어 문장만 봅니다. 한국어 문장은 문장 나누기부터 맞지 않습니다.
- 정규식이라 **뜻이 아니라 말버릇**만 봅니다. `restate`가 낱말 겹침으로만 재기
  때문에, 같은 말을 낱말까지 완전히 바꿔 되풀이하면 놓칩니다.
- 오탐이 있습니다. `X-level`(`participant-level` 등)을 넓게 잡기로 한 결과가 가장
  자주 걸리고, `beat`도 짧은 문장을 잘못 집을 때가 있습니다. 거슬리면
  `--only`로 갈래를 좁히거나 `--min-level medium` 으로 약한 것을 빼세요.
- 지적이 없다고 사람이 썼다는 뜻이 아니고, 지적이 많다고 기계가 썼다는 뜻도 아닙니다.
  이 도구는 **고쳐 쓸 자리**를 짚는 것이지 저자를 판정하지 않습니다.
