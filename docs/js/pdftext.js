// pdf.js 로 PDF → 줄 목록.
//
// pdftotext 와 달리 글자 좌표를 직접 받으므로 세 가지를 우리가 제어한다:
//   1) 2단 조판을 단별로 나눈 뒤 읽기 순서대로 이어붙인다
//   2) 여백 줄번호(투고본)를 좌표로 알아보고 지운다
//   3) 문단이 어디서 시작하는지 줄 간격과 들여쓰기로 판단한다
//      (pdftotext 판은 빈 줄에 기대야 해서 여백 줄번호가 있으면 흔들린다)

const GUTTER_BINS = 120;

function itemsOfPage(textContent) {
  const out = [];
  for (const it of textContent.items) {
    if (!it.str || !it.str.trim()) continue;
    const t = it.transform;
    out.push({
      str: it.str,
      x: t[4],
      y: t[5],
      w: it.width || 0,
      h: it.height || Math.abs(t[3]) || 10,
    });
  }
  return out;
}

/** 페이지 가운데의 빈 세로띠(gutter)를 찾아 단 경계 x 좌표를 돌려준다 */
function detectGutter(items, pageWidth) {
  if (items.length < 40) return null;
  const hist = new Array(GUTTER_BINS).fill(0);
  for (const it of items) {
    const a = Math.max(0, Math.floor((it.x / pageWidth) * GUTTER_BINS));
    const b = Math.min(GUTTER_BINS - 1, Math.floor(((it.x + it.w) / pageWidth) * GUTTER_BINS));
    for (let i = a; i <= b; i++) hist[i]++;
  }
  // 머리글처럼 가운데를 살짝 침범하는 줄이 있으므로 완전한 0 대신 여유를 둔다
  const slack = Math.max(0, Math.floor(items.length * 0.005));
  const lo = Math.floor(GUTTER_BINS * 0.32);
  const hi = Math.floor(GUTTER_BINS * 0.68);

  let best = null, run = null;
  for (let i = lo; i <= hi; i++) {
    if (hist[i] <= slack) {
      run = run ? { s: run.s, e: i } : { s: i, e: i };
      if (!best || run.e - run.s > best.e - best.s) best = { ...run };
    } else run = null;
  }
  if (!best || best.e - best.s < 2) return null;

  const cut = (((best.s + best.e + 1) / 2) / GUTTER_BINS) * pageWidth;
  const left = items.filter(it => it.x + it.w / 2 < cut).length;
  if (left < items.length * 0.2 || left > items.length * 0.8) return null;
  return cut;
}

const INT_RE = /^\d{1,5}$/;

/**
 * 여백의 줄번호를 지운다 (ACM 투고 양식 등).
 * 본문과 y 가 거의 같아서 그대로 두면 문장 한가운데로 섞여 들어간다.
 */
function dropLineNumbers(items) {
  const nums = items.filter(it => INT_RE.test(it.str.trim()));
  if (nums.length < 8) return items;

  const bins = new Map();                       // x(3pt 단위) → 정수 아이템
  for (const it of nums) {
    const k = Math.round(it.x / 3);
    if (!bins.has(k)) bins.set(k, []);
    bins.get(k).push(it);
  }

  const drop = new Set();
  for (const [k, group] of bins) {
    if (group.length < 8) continue;
    // 같은 세로줄에 놓인 아이템이 거의 전부 숫자여야 여백 줄번호다
    const band = items.filter(it => Math.abs(it.x - k * 3) <= 3);
    if (group.length / band.length < 0.9) continue;
    // 위에서 아래로 대체로 증가해야 한다
    const seq = [...group].sort((a, b) => b.y - a.y).map(it => +it.str.trim());
    let inc = 0;
    for (let i = 1; i < seq.length; i++) if (seq[i] > seq[i - 1]) inc++;
    if (inc < (seq.length - 1) * 0.8) continue;
    for (const it of group) drop.add(it);
  }
  return drop.size ? items.filter(it => !drop.has(it)) : items;
}

/**
 * 같은 y 에 있는 조각들을 한 줄로 묶고, 조각 사이 간격을 보고 공백을 넣는다.
 * 줄마다 {text, x, y, h} 를 돌려준다 (문단 시작 판단에 쓴다).
 */
function buildLines(items) {
  if (!items.length) return [];
  const heights = items.map(i => i.h).sort((a, b) => a - b);
  const medH = heights[Math.floor(heights.length / 2)] || 10;
  const tol = Math.max(2, medH * 0.5);

  const sorted = [...items].sort((a, b) => b.y - a.y || a.x - b.x);
  const rows = [];
  let cur = null;
  for (const it of sorted) {
    if (!cur || Math.abs(it.y - cur.y) > tol) {
      cur = { y: it.y, items: [it] };
      rows.push(cur);
    } else {
      cur.items.push(it);
      cur.y = (cur.y * (cur.items.length - 1) + it.y) / cur.items.length;
    }
  }

  const out = [];
  for (const ln of rows) {
    ln.items.sort((a, b) => a.x - b.x);
    let s = '';
    let prev = null;
    for (const it of ln.items) {
      if (prev) {
        const gap = it.x - (prev.x + prev.w);
        if (gap > prev.h * 0.18 && !/\s$/.test(s) && !/^\s/.test(it.str)) s += ' ';
      }
      s += it.str;
      prev = it;
    }
    s = s.replace(/\s+/g, ' ').trim();
    if (s) out.push({ text: s, x: ln.items[0].x, y: ln.y, h: medH });
  }
  return out;
}

/**
 * 문단이 새로 시작하는 줄을 표시한다.
 * 줄 간격이 평소보다 벌어졌거나, 왼쪽 끝이 들여쓰기됐으면 새 문단으로 본다.
 */
function markBreaks(rows) {
  if (rows.length < 3) {
    rows.forEach((r, i) => { r.brk = i === 0; });
    return rows;
  }
  const gaps = [];
  for (let i = 1; i < rows.length; i++) gaps.push(rows[i - 1].y - rows[i].y);
  const pitch = [...gaps].sort((a, b) => a - b)[Math.floor(gaps.length / 2)] || rows[0].h;
  const lefts = [...rows.map(r => r.x)].sort((a, b) => a - b);
  const leftEdge = lefts[Math.floor(lefts.length * 0.25)];

  rows.forEach((r, i) => {
    if (i === 0) { r.brk = true; return; }
    const gap = rows[i - 1].y - r.y;
    r.brk = gap > pitch * 1.35 || r.x - leftEdge > r.h * 0.6;
  });
  return rows;
}

const mask = l => l.replace(/\d+/g, '#');

/** 쪽번호만 바뀌는 머리글 후보인가 ("24 Anon." 는 예, "#–#." 는 아님) */
function headLike(l) {
  if (/(?:doi:|https?:|10\.\d)/i.test(l)) return false;
  const letters = (l.match(/[A-Za-zÀ-ɏ]/g) || []).length;
  return letters / l.length >= 0.5 && /[A-Za-z]{3,}/.test(l);
}

/**
 * 페이지마다 반복되는 머리글/바닥글 제거.
 *
 * 글자가 똑같이 반복되면 어디에 있든 지운다. 쪽번호가 섞여 매번 달라지는
 * "24 Anon." 류는 숫자를 가린 형태로 세되, 본문을 잘못 지우지 않도록
 * 페이지의 맨 위/아래 두 줄에만 적용한다.
 */
export function stripRunningHeads(pageRows, minRepeat = 4) {
  const exact = new Map();
  const masked = new Map();
  for (const page of pageRows) {
    page.forEach((r, i) => {
      const k = r.text.trim();
      if (!k) return;
      exact.set(k, (exact.get(k) || 0) + 1);
      if (i < 2 || i >= page.length - 2) masked.set(mask(k), (masked.get(mask(k)) || 0) + 1);
    });
  }

  const removed = new Set();
  const lines = [];
  pageRows.forEach((page, pi) => {
    page.forEach((r, i) => {
      const k = r.text.trim();
      if (!k) return;
      if (k.length >= 5) {
        if (k.length <= 150 && (exact.get(k) || 0) >= minRepeat) { removed.add(k); return; }
        const edge = i < 2 || i >= page.length - 2;
        if (edge && k.length <= 120 && headLike(k) && (masked.get(mask(k)) || 0) >= minRepeat) {
          removed.add(mask(k));
          return;
        }
      }
      lines.push({ text: r.text, page: pi + 1, brk: Boolean(r.brk) });
    });
  });
  return { lines, removed: [...removed] };
}

/**
 * @returns {Promise<{lines: {text: string, page: number, brk: boolean}[],
 *                    pages: number, columns: number[], removedHeads: string[]}>}
 */
export async function extractText(pdfjsLib, arrayBuffer, onProgress) {
  const task = pdfjsLib.getDocument({
    data: arrayBuffer,
    isEvalSupported: false,
    disableFontFace: true,
  });
  const doc = await task.promise;
  const numPages = doc.numPages;

  const pageRows = [];
  const columns = [];
  for (let p = 1; p <= numPages; p++) {
    const page = await doc.getPage(p);
    const viewport = page.getViewport({ scale: 1 });
    const items = dropLineNumbers(itemsOfPage(await page.getTextContent()));
    const cut = detectGutter(items, viewport.width);
    columns.push(cut ? 2 : 1);

    if (cut === null) {
      pageRows.push(markBreaks(buildLines(items)));
    } else {
      const left = [], right = [];
      for (const it of items) (it.x + it.w / 2 < cut ? left : right).push(it);
      pageRows.push([...markBreaks(buildLines(left)), ...markBreaks(buildLines(right))]);
    }
    page.cleanup();
    onProgress?.(p, numPages);
  }
  await task.destroy();

  const { lines, removed } = stripRunningHeads(pageRows);
  return { lines, pages: numPages, columns, removedHeads: removed };
}
