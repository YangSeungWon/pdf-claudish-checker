// 화면 문구. 갈래 이름과 조언은 rules.json 에 들어 있어 여기서 다시 쓰지 않는다.

const STR = {
  en: {
    title: 'Claudish Checker',
    tagline: 'Find Claude-flavoured sentences in a paper draft.',
    newFile: 'Another PDF',
    footPrivacy: 'runs in your browser',
    drop: 'Drop a PDF here',
    dropSub: 'or click to choose',
    run: 'Check',
    strict: 'include ordinary terms',
    strictTip: 'On by default. Also flags words that are often legitimate terminology — provenance, canonical, drift, X-level, protocol. Uncheck to leave them alone.',
    reading: 'Reading',
    extracting: 'Extracting text',
    scanning: 'Scanning sentences',
    page: 'pages',
    pageShort: 'p.',
    meta: (s, w, f) => `${s} sentences · ${w} words · ${f} flagged`,
    noProse: 'No body sentences found. Check the extracted text below.',
    error: 'Error',
    pdfOnly: 'PDF files only.',
    score: 'claudish score',
    per: 'per 1000 words',
    band: {
      clean: 'clean', light: 'light', some: 'noticeable', heavy: 'heavy',
    },
    bandNote: {
      clean: 'Nothing that reads as machine style.',
      light: 'A few habits worth a second look.',
      some: 'Enough of it to be visible to a reader.',
      heavy: 'The style dominates. Worth a rewrite pass.',
    },
    level: { strong: 'strong', medium: 'medium', weak: 'weak' },
    levelTip: {
      strong: 'Almost never appears in a paper written by hand.',
      medium: 'A habit worth cutting, but it has legitimate uses.',
      weak: 'A hint on its own. Read it together with the rest.',
    },
    allOk: 'Nothing to flag.',
    clearFilter: 'Show all',
    filterCount: (n, total) => `${n} of ${total} sentences`,
    restate: {
      neighbor: 'repeats the previous sentence',
      clause: 'repeats itself across the dash or colon',
    },
    beat: {
      short: 'a verdict line dropped after a long sentence',
      anaphora: 'the third sentence in a row opening the same way',
    },
    prev: 'Previous sentence',
    terms: "Excluded as the paper's own terminology",
    debug: 'Extracted body text',
    heads: 'Removed running heads',
    hlFlagged: (n) => `${n} sentence${n === 1 ? '' : 's'} worth a look.`,
    hlNone: 'No sentence tripped a rule.',
  },
  ko: {
    title: 'Claudish 체커',
    tagline: '논문 초고에서 Claude가 쓴 것 같은 문장을 찾습니다.',
    newFile: '다른 PDF',
    footPrivacy: '브라우저에서만 실행',
    drop: 'PDF를 여기에 놓으세요',
    dropSub: '또는 클릭해서 선택',
    run: '검사',
    strict: '정식 용어까지',
    strictTip: '켜 두면 provenance·canonical·drift·X-level·protocol 처럼 정식 용어로도 흔히 쓰이는 낱말까지 지적합니다. 기본은 켜져 있고, 끄면 이런 낱말은 넘어갑니다.',
    reading: '읽는 중',
    extracting: '텍스트 추출',
    scanning: '문장 검사',
    page: '쪽',
    pageShort: '쪽',
    meta: (s, w, f) => `문장 ${s}개 · 단어 ${w}개 · 그중 ${f}개 지적`,
    noProse: '본문 문장을 찾지 못했습니다. 아래 \'뽑아낸 본문\'을 보세요.',
    error: '오류',
    pdfOnly: 'PDF 파일만 열 수 있습니다.',
    score: 'claudish 지수',
    per: '1000단어당',
    band: {
      clean: '깨끗함', light: '옅음', some: '눈에 띔', heavy: '짙음',
    },
    bandNote: {
      clean: '기계가 쓴 것처럼 읽힐 대목이 없습니다.',
      light: '다시 볼 만한 대목이 조금 있습니다.',
      some: '읽는 사람이 알아챌 만큼 쌓였습니다.',
      heavy: '문체가 내용을 덮고 있습니다. 한 번 고쳐 쓰는 게 좋겠습니다.',
    },
    level: { strong: '강함', medium: '중간', weak: '약함' },
    levelTip: {
      strong: '사람이 손으로 쓴 논문에는 거의 나오지 않는 표현입니다.',
      medium: '고칠 만한 버릇이지만 제대로 쓰이는 자리도 있습니다.',
      weak: '이것 하나로는 단서일 뿐입니다. 나머지와 함께 보세요.',
    },
    allOk: '짚을 문장이 없습니다.',
    clearFilter: '전체 보기',
    filterCount: (n, total) => `지적 ${total}개 중 ${n}개`,
    restate: {
      neighbor: '앞 문장과 같은 말',
      clause: '문장 안에서 같은 말을 되풀이',
    },
    beat: {
      short: '긴 문장 뒤에 붙인 한 마디',
      anaphora: '같은 첫머리로 세 문장째',
    },
    prev: '앞 문장',
    terms: '이 글이 쓰는 용어로 보고 뺀 것',
    debug: '뽑아낸 본문',
    heads: '지운 머리글·바닥글',
    hlFlagged: (n) => `다시 볼 문장 ${n}개.`,
    hlNone: '걸린 문장이 없습니다.',
  },
};

const KEY = 'claudish.lang';
let lang = localStorage.getItem(KEY)
  || (navigator.language?.toLowerCase().startsWith('ko') ? 'ko' : 'en');

export const t = () => STR[lang];
export const getLang = () => lang;
export function setLang(l) {
  lang = STR[l] ? l : 'en';
  localStorage.setItem(KEY, lang);
  document.documentElement.lang = lang;
}
export const LANGS = Object.keys(STR);
