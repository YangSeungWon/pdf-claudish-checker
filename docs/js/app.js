import * as pdfjsLib from '../vendor/pdfjs/pdf.min.mjs';
import { extractText } from './pdftext.js';
import { compileRules, analyze, LEVEL_ORDER } from './detect.js';
import { t, getLang, setLang, LANGS } from './i18n.js';

pdfjsLib.GlobalWorkerOptions.workerSrc =
  new URL('../vendor/pdfjs/pdf.worker.min.mjs', import.meta.url).href;

const LANG_NAME = { en: 'EN', ko: '한국어' };
const MARK = { strong: '✗', medium: '⚠', weak: '·' };

const $ = s => document.querySelector(s);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

let RULES = null;
let report = null;
let picked = null;
let busy = false;
let filter = null;
let strict = true;

const detOf = id => RULES.detectors.find(d => d.id === id);
const labelOf = id => detOf(id).label[getLang()] || detOf(id).label.en;
const adviceOf = id => detOf(id).advice[getLang()] || detOf(id).advice.en;

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------

function applyStatic() {
  document.title = t().title;
  for (const n of document.querySelectorAll('.opt')) n.title = t().strictTip;
  for (const n of document.querySelectorAll('[data-i18n]')) {
    const v = t()[n.dataset.i18n];
    if (typeof v === 'string') n.textContent = v;
  }
  const box = $('#lang');
  box.innerHTML = '';
  for (const l of LANGS) {
    const b = el('button', null, LANG_NAME[l] || l);
    b.setAttribute('aria-pressed', String(l === getLang()));
    b.onclick = () => { setLang(l); applyStatic(); if (report) render(); };
    box.append(b);
  }
}

// ---------------------------------------------------------------------------
// 검사
// ---------------------------------------------------------------------------

const setStatus = msg => { $('#status').textContent = msg; };

function setProgress(done, total, unit, stage) {
  $('#progress').hidden = false;
  $('#pg-n').textContent = String(done);
  $('#pg-t').textContent = String(total);
  $('#pg-u').textContent = unit;
  $('#pg-sub').textContent = stage;
  $('#bar').style.width = `${total ? Math.round((done / total) * 100) : 0}%`;
}

async function run(file) {
  if (busy) return;
  busy = true;
  filter = null;
  $('#run').disabled = true;
  $('#results').innerHTML = '';
  $('#summary').hidden = true;
  $('#restart').hidden = true;

  try {
    setProgress(0, 1, '', `${t().reading} ${file.name}`);
    const buf = await file.arrayBuffer();
    const doc = await extractText(pdfjsLib, buf, (p, n) =>
      setProgress(p, n, t().page, t().extracting));

    setProgress(doc.pages, doc.pages, t().page, t().scanning);
    const rep = analyze(doc.lines, RULES, strict);
    report = { file: file.name, doc, ...rep };

    $('#progress').hidden = true;
    setStatus('');
    $('#pick').hidden = true;
    $('#filebar').hidden = false;
    $('#fb-name').textContent = file.name;
    $('#restart').hidden = false;
    render();
  } catch (e) {
    $('#progress').hidden = true;
    setStatus(`${t().error}: ${e.message}`);
    console.error(e);
  } finally {
    busy = false;
    $('#run').disabled = false;
  }
}

// ---------------------------------------------------------------------------
// 그리기
// ---------------------------------------------------------------------------

function renderSummary() {
  const box = $('#summary');
  box.hidden = false;
  box.innerHTML = '';

  const head = el('div', 'sum-total');
  const n = el('b', null, String(report.score));
  head.append(n, ` ${t().per} `);
  const b = el('span', `band ${report.band}`, t().band[report.band]);
  head.append(b);
  box.append(head);
  box.append(el('p', 'sum-note', t().bandNote[report.band]));

  box.append(el('p', 'sum-meta', t().meta(
    report.sentences.length.toLocaleString(),
    report.words.toLocaleString(),
    report.flagged.length.toLocaleString())));

  const ids = RULES.detectors.map(d => d.id).filter(id => report.counts[id]);
  if (ids.length) {
    const legend = el('div', 'legend');
    for (const id of ids) {
      const d = detOf(id);
      const chip = el('button', `chip ${d.level}`);
      chip.title = t().levelTip[d.level];
      chip.append(el('b', null, String(report.counts[id])), el('span', null, labelOf(id)));
      chip.classList.toggle('on', filter === id);
      chip.classList.toggle('off', filter !== null && filter !== id);
      chip.onclick = () => { filter = filter === id ? null : id; render(); };
      legend.append(chip);
    }
    box.append(legend);
  }

  if (report.terms.length) {
    const line = report.terms.map(x => `${x.text} (${x.count})`).join(', ');
    box.append(el('p', 'sum-terms', `${t().terms}: ${line}`));
  }
}

/** 문장을 조각내어 히트 구간에 표시를 붙인다 */
function sentenceNode(s, hits) {
  const wrap = el('p', 'sent');
  const spans = hits
    .filter(h => h.end > h.start && !h.kind)
    .map(h => [h.start, h.end, h.id])
    .sort((a, b) => a[0] - b[0]);

  const merged = [];
  for (const [a, b, id] of spans) {
    const last = merged[merged.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b);
    else merged.push([a, b, id]);
  }

  let pos = 0;
  for (const [a, b, id] of merged) {
    if (a > pos) wrap.append(s.text.slice(pos, a));
    wrap.append(el('mark', detOf(id).level, s.text.slice(a, b)));
    pos = b;
  }
  wrap.append(s.text.slice(pos));
  return wrap;
}

function renderResults() {
  const box = $('#results');
  box.innerHTML = '';

  const shown = [];
  for (const s of report.flagged) {
    const hits = filter ? s.hits.filter(h => h.id === filter) : s.hits;
    if (hits.length) shown.push({ s, hits });
  }

  const head = el('p', 'headline');
  head.textContent = shown.length ? t().hlFlagged(shown.length) : t().hlNone;
  box.append(head);

  if (filter) {
    const bar = el('div', `filterbar ${detOf(filter).level}`);
    bar.append(el('span', 'fb-what', labelOf(filter)));
    bar.append(el('span', 'fb-count', t().filterCount(shown.length, report.flagged.length)));
    const clear = el('button', 'clear', t().clearFilter);
    clear.onclick = () => { filter = null; render(); };
    bar.append(clear);
    box.append(bar);
  }

  if (!shown.length) {
    box.append(el('p', 'ok', t().allOk));
    return;
  }

  const list = el('div', 'sentlist');
  for (const { s, hits } of shown) {
    const worst = hits.reduce((a, h) =>
      LEVEL_ORDER[h.level] > LEVEL_ORDER[a.level] ? h : a, hits[0]);
    const row = el('div', `row ${worst.level}`);

    const gut = el('div', 'gut');
    gut.append(el('span', `mk ${worst.level}`, MARK[worst.level]));
    gut.append(el('span', 'pg', `${t().pageShort}${s.page}`));
    row.append(gut);

    const body = el('div', 'body');
    const withPrev = hits.find(h => h.prev !== undefined);
    if (withPrev) {
      const prev = report.sentences[withPrev.prev];
      if (prev) {
        const q = el('p', 'prev');
        q.append(el('span', 'prev-k', t().prev), prev.text);
        body.append(q);
      }
    }
    body.append(sentenceNode(s, hits));

    const why = el('ul', 'why');
    for (const h of [...hits].sort((a, b) => LEVEL_ORDER[b.level] - LEVEL_ORDER[a.level])) {
      const li = el('li', h.level);
      li.append(el('span', 'why-k', labelOf(h.id)));
      const what = (h.id === 'restate' || h.id === 'beat')
        ? t()[h.id][h.kind] || ''
        : `“${h.text}”`;
      if (what) li.append(el('span', 'why-m', what));
      li.append(el('span', 'why-a', adviceOf(h.id)));
      why.append(li);
    }
    body.append(why);
    row.append(body);
    list.append(row);
  }
  box.append(list);
}

function renderDebug() {
  const box = $('#debug');
  const body = $('#debug-body');
  body.innerHTML = '';
  if (!report) { box.hidden = true; return; }
  box.hidden = false;
  if (report.doc?.removedHeads?.length) {
    body.append(el('p', 'note', `${t().heads}: ${report.doc.removedHeads.join(' · ')}`));
  }
  const dump = el('div', 'dump',
    report.sentences.map(s => `[${s.page}] ${s.text}`).join('\n'));
  body.append(dump);
}

function render() {
  if (!report) return;
  if (!report.sentences.length) {
    setStatus(t().noProse);
    $('#summary').hidden = true;
    renderDebug();
    return;
  }
  renderSummary();
  renderResults();
  renderDebug();
}

// ---------------------------------------------------------------------------
// 파일 고르기
// ---------------------------------------------------------------------------

async function preview(file) {
  picked = file;
  $('#drop').hidden = true;
  $('#preview').hidden = false;
  $('#run-row').hidden = false;
  $('#filename').textContent = file.name;
  try {
    const buf = await file.arrayBuffer();
    const doc = await pdfjsLib.getDocument({ data: buf.slice(0), isEvalSupported: false }).promise;
    $('#pv-pages').textContent = `${doc.numPages} ${t().page}`;
    const page = await doc.getPage(1);
    const vp = page.getViewport({ scale: 1 });
    const scale = 150 / vp.width;
    const v = page.getViewport({ scale });
    const canvas = $('#thumb');
    canvas.width = v.width;
    canvas.height = v.height;
    await page.render({ canvasContext: canvas.getContext('2d'), viewport: v }).promise;
    await doc.destroy();
  } catch { /* 미리보기 실패는 검사와 무관 */ }
}

function reset() {
  report = null;
  picked = null;
  filter = null;
  $('#pick').hidden = false;
  $('#drop').hidden = false;
  $('#preview').hidden = true;
  $('#run-row').hidden = true;
  $('#filebar').hidden = true;
  $('#summary').hidden = true;
  $('#results').innerHTML = '';
  $('#debug').hidden = true;
  $('#restart').hidden = true;
  setStatus('');
}

function accept(file) {
  if (!file) return;
  if (file.type !== 'application/pdf' && !/\.pdf$/i.test(file.name)) {
    setStatus(t().pdfOnly);
    return;
  }
  setStatus('');
  preview(file);
}

function wire() {
  $('#drop').onclick = () => $('#file').click();
  $('#drop').onkeydown = e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#file').click(); }
  };
  $('#file').onchange = e => accept(e.target.files[0]);
  $('#change').onclick = reset;
  $('#reset').onclick = reset;
  $('#reset-bottom').onclick = reset;
  $('#run').onclick = () => picked && run(picked);
  $('#strict').checked = strict;
  $('#strict2').checked = strict;
  $('#strict').onchange = e => { strict = e.target.checked; $('#strict2').checked = strict; };
  $('#strict2').onchange = e => {
    strict = e.target.checked;
    $('#strict').checked = strict;
    if (report) {                       // 다시 읽을 필요 없이 판정만 새로 한다
      filter = null;
      report = { ...report, ...analyze(report.doc.lines, RULES, strict) };
      render();
    }
  };

  let depth = 0;
  document.addEventListener('dragenter', e => {
    e.preventDefault();
    if (depth++ === 0) document.body.classList.add('dragging');
  });
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('dragleave', () => {
    if (--depth <= 0) { depth = 0; document.body.classList.remove('dragging'); }
  });
  document.addEventListener('drop', e => {
    e.preventDefault();
    depth = 0;
    document.body.classList.remove('dragging');
    accept(e.dataTransfer?.files?.[0]);
  });
}

(async function init() {
  setLang(getLang());
  applyStatic();
  wire();
  $('#pdfjs-version').textContent = pdfjsLib.version || '?';
  try {
    const res = await fetch(new URL('../rules.json', import.meta.url));
    RULES = compileRules(await res.json());
  } catch (e) {
    setStatus(`${t().error}: rules.json — ${e.message}`);
  }
})();
