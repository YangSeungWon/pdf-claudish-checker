// PDF 에서 뽑은 줄 → 본문 문단 → 문장.
// 파이썬판 claudish_check.py 의 같은 이름 함수들을 그대로 옮긴 것이라,
// 같은 텍스트를 넣으면 문장 목록이 글자 하나까지 같아야 한다.

const TAIL_RE =
  /^[ \t]*(?:\d+[.\s]*)?(?:REFERENCES|References|Bibliography|BIBLIOGRAPHY|Works\s+Cited|참고\s*문헌)[ \t]*$/;

const URL_RE = /https?:\/\/\S+|\bdoi:\s*\S+|\b10\.\d{4,9}\/\S+/gi;
const CITE_RE = /\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]/g;

const DASHES = /[‐‑‒–―−]/g;
const SQUOTES = /[‘’ʼ]/g;
const DQUOTES = /[“”]/g;

/** 표시용 정리. 줄표(—)는 세는 대상이라 남긴다. */
export function clean(s) {
  let t = String(s ?? '').normalize('NFKC');
  t = t.replace(/ﬀ/g, 'ff').replace(/ﬁ/g, 'fi').replace(/ﬂ/g, 'fl')
       .replace(/ﬃ/g, 'ffi').replace(/ﬄ/g, 'ffl');
  t = t.replace(DASHES, '-').replace(SQUOTES, "'").replace(DQUOTES, '"');
  return t.replace(/\s+/g, ' ').trim();
}

const ENDS_RE = /[.!?:,;"')\]-]$/;
const NUM_HEAD_RE = /^[0-9]+(?:\.[0-9]+)*\.?\s+[A-Z]/;
const BARE_NUM_RE = /^[0-9]{1,4}$/;
const SENT_END_RE = /[.!?]["')\]]?$/;

// 파이썬은 문자(코드포인트) 단위로 세고 JS 의 .length 는 UTF-16 단위라
// 수식 기호(𝑚 같은 astral 문자)가 섞이면 비율이 달라진다. 둘을 맞춘다.
function cps(s) {
  return [...s].length;
}

function letterCount(s) {
  let n = 0;
  for (const ch of s) if (/\p{L}/u.test(ch)) n++;
  return n;
}

/** 절 제목·수식·표처럼 문장이 아닌 줄인가 */
export function skipLine(line) {
  const s = line.trim();
  const len = cps(s);
  if (len < 3) return true;
  const letters = letterCount(s);
  if (letters < 3 || letters / len < 0.55) return true;
  if (/\p{Lu}/u.test(s) && !/[\p{Ll}\p{Lt}]/u.test(s)) return true;   // 파이썬 str.isupper()
  if (len < 75 && !ENDS_RE.test(s)) {
    if (NUM_HEAD_RE.test(s)) return true;
    const w = s.split(/\s+/);
    const caps = w.filter(x => /^\p{Lu}/u.test(x)).length;
    if (w.length <= 9 && caps >= Math.max(2, w.length * 0.6)) return true;
  }
  return false;
}

/**
 * 평문을 줄 레코드로. CLI 와 결과를 맞추기 위한 입구.
 * @returns {{text: string, page: number, brk: boolean}[]}
 */
export function linesFromText(text) {
  const out = [];
  let page = 1;
  let blank = false;
  for (let raw of text.split('\n')) {
    if (raw.includes('\f')) {
      page += (raw.match(/\f/g) || []).length;
      raw = raw.replace(/\f/g, ' ');
    }
    if (!raw.trim()) { blank = true; continue; }
    out.push({ text: raw, page, brk: blank });
    blank = false;
  }
  return out;
}

/**
 * 줄 레코드 → 본문 문단. 각 문단은 {text, page} 줄 묶음.
 *
 * brk(앞에 문단 경계 신호가 있었다) 는 앞 줄이 문장부호로 끝났을 때만 믿는다.
 * 투고본은 여백 줄번호 때문에 문장 한가운데에 빈 줄이 들어가기 때문이다.
 */
export function paragraphs(lines, rules) {
  let end = lines.length;
  for (let i = 0; i < lines.length; i++) {
    if (TAIL_RE.test(lines[i].text)) end = i;         // 마지막 References 헤딩
  }

  const paras = [];
  let cur = [];
  let pending = false;
  const flush = () => { if (cur.length) { paras.push(cur); cur = []; } };

  for (let i = 0; i < end; i++) {
    const rec = lines[i];
    if (rec.brk) pending = true;
    const line = rec.text.replace(URL_RE, ' ').replace(CITE_RE, ' ').trim();
    if (!line) { pending = true; continue; }
    if (BARE_NUM_RE.test(line)) continue;             // 여백 줄번호 · 쪽번호
    if (skipLine(line)) { flush(); pending = false; continue; }
    if (pending && cur.length && SENT_END_RE.test(cur[cur.length - 1].text)) flush();
    pending = false;
    cur.push({ text: line, page: rec.page });
  }
  flush();

  return paras.filter(p => {
    const joined = p.map(l => l.text).join(' ');
    return !rules._boiler.some(b => b.test(joined));
  });
}

/** 문단의 줄을 이어 붙이고 글자 위치 → 쪽 대응표를 함께 만든다 */
export function joinLines(lines) {
  let out = '';
  const marks = [];
  for (const { text, page } of lines) {
    if (out) {
      if (out.endsWith('-') && /^[a-z]/.test(text)) out = out.slice(0, -1);
      else out += ' ';
    }
    marks.push([out.length, page]);
    out += text;
  }
  return { text: clean(out), marks };
}

// ---------------------------------------------------------------------------
// 문장 나누기
// ---------------------------------------------------------------------------

const ABBREV = new Set([
  'e.g.', 'i.e.', 'cf.', 'al.', 'et.', 'etc.', 'fig.', 'figs.', 'eq.', 'eqs.',
  'vs.', 'dr.', 'mr.', 'mrs.', 'ms.', 'prof.', 'approx.', 'no.', 'nos.', 'pp.',
  'p.', 'ch.', 'chap.', 'sec.', 'sect.', 'tab.', 'vol.', 'ed.', 'eds.', 'est.',
  'inc.', 'ltd.', 'st.', 'jr.', 'sr.', 'min.', 'max.', 'ca.', 'resp.', 'viz.',
  'ibid.', 'vs', 'al',
]);

const BREAK_RE = /[.!?]["')\]]*(\s+)/g;
const TAIL_TOK_RE = /[A-Za-z0-9.]+$/;
const NEXT_RE = /^[A-Z0-9"'(\[]/;

function isAbbrev(head) {
  const m = TAIL_TOK_RE.exec(head);
  if (!m) return false;
  const tok = m[0].toLowerCase();
  return ABBREV.has(tok) || /^[a-z]\.$/.test(tok) || /^[0-9]+\.$/.test(tok);
}

/** @returns {[number, string][]} (문단 안 시작 위치, 문장) */
export function splitSentences(para) {
  const out = [];
  let start = 0;
  BREAK_RE.lastIndex = 0;
  let m;
  while ((m = BREAK_RE.exec(para)) !== null) {
    const end = m.index + m[0].length - m[1].length;
    const after = m.index + m[0].length;
    const next = para.slice(after);
    if (!next) break;
    if (isAbbrev(para.slice(0, end)) || !NEXT_RE.test(next)) continue;
    const s = para.slice(start, end).trim();
    if (s) out.push([start, s]);
    start = after;
  }
  const tail = para.slice(start).trim();
  if (tail) out.push([start, tail]);
  return out;
}

export const WORD_RE = /[A-Za-z][A-Za-z0-9']*/g;

export function words(s) {
  return s.match(WORD_RE) || [];
}

/** 문장으로 셀 만한가. 표 조각·수식 찌꺼기를 걸러낸다. */
export function isProse(s, minWords) {
  if (words(s).length < minWords) return false;
  if (!/[a-z]{2}/.test(s)) return false;
  return letterCount(s) / cps(s) >= 0.6;
}
