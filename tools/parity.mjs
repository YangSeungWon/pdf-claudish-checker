// 웹 판정 로직을 node 로 돌려 JSON 으로 뱉는다. CLI 와 대조하기 위한 것.
//   node tools/parity.mjs body.txt > web.json
import { readFileSync } from 'node:fs';
import { compileRules, analyze } from '../docs/js/detect.js';
import { linesFromText } from '../docs/js/prose.js';

const rules = compileRules(JSON.parse(readFileSync(
  new URL('../docs/rules.json', import.meta.url), 'utf8')));
const text = readFileSync(process.argv[2], 'utf8');
const rep = analyze(linesFromText(text), rules);

process.stdout.write(JSON.stringify({
  words: rep.words,
  sentences: rep.sentences.length,
  score: rep.score,
  band: rep.band,
  counts: rep.counts,
  terms: rep.terms,
  flagged: rep.flagged.map(s => ({
    page: s.page,
    text: s.text,
    hits: s.hits.map(h => ({ id: h.id, start: h.start, end: h.end, text: h.text,
                             kind: h.kind ?? null })),
  })),
}, null, 2) + '\n');
