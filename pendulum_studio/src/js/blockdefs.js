/* 블록 정의.
 *
 * 범주 이름·색·순서와 블록 모양은 엔트리를 따릅니다 (app/design/블록_UI_개선_설계안.md).
 *   stk  쌓기 블록 — 왼쪽 위 V 홈, 왼쪽 아래 V 돌기, 오른쪽 끝 반원
 *   c    감싸는 블록 — 만일 ~ (이)라면
 *   val  값 블록 — 둥근 캡슐. 숫자 칸에 끼웁니다
 *   bool 판단 블록 — 육각. 육각 칸에만 끼웁니다
 *
 * tpl 은 블록에 적히는 글과 칸이 번갈아 오는 목록입니다.
 *   "글"                         그대로 적는 글
 *   { s: "num", v: 10 }          숫자 칸 (값 블록을 끼울 수 있음), v 는 처음 값
 *   { s: "bool" }                육각 칸 (판단 블록만)
 *   { dd: "이름", opts: [[값, 글], ...] }   고르는 칸
 *
 * dom 은 쌓기 블록이 들어갈 수 있는 묶음입니다. reward = 점수 규칙, run = 시작하기 아래.
 *
 * 높이·빠르기·힘 값은 0~100, 기울기·팔 각도는 도 단위입니다. 기본 값은 방향을 제거하고,
 * 고급 그룹은 부호 있는 각도(도)·각속도(rad/s)를 제공합니다. v = { phi, ald, thd, u, th }.
 * phi 는 직립 오차(rad), th 는 누적 팔 각도(rad)입니다. 다른 단위의 크기는 그대로 비교하지 않습니다.
 */
(function (PS) {
  "use strict";

  var PEND_SPEED_MAX = 25.0;
  var ARM_SPEED_MAX = 19.2;
  var DEG = 180 / Math.PI;

  var CATS = [
    { key: "start", name: "시작", color: "#00b400", dark: "#009400", glyph: "▶", note: "프로그램이 시작되는 곳" },
    { key: "flow", name: "흐름", color: "#19baea", dark: "#1498c0", glyph: "⤴", note: "조건에 따라 실행하기" },
    { key: "judge", name: "판단", color: "#4562f5", dark: "#1b3ad8", glyph: "✓", note: "참인지 거짓인지" },
    { key: "calc", name: "계산", color: "#f4af18", dark: "#ff7f00", glyph: "＋", note: "숫자 계산" },
    { key: "score", name: "점수", color: "#dd47d8", dark: "#b819b3", glyph: "★", note: "보상(점수) 규칙" },
    { key: "kit", name: "키트", color: "#00b6b1", dark: "#008f8b", glyph: "⚙", note: "키트가 재는 값" },
    { key: "ai", name: "인공지능", color: "#8222ff", dark: "#6100d6", glyph: "AI", note: "가르치고 시험하기" }
  ];

  function clamp100(x) { return x < 0 ? 0 : x > 100 ? 100 : x; }
  var LEVELS = [[0, "감점 없음"], [1, "약하게 감점"], [2, "강하게 감점"]];

  var DEFS = {
    /* ── 키트: 값 (0~100) ── */
    height: { cat: "kit", shape: "val", tpl: ["진자 높이 (0~100)"], group: "크기로 보기 · 0~100",
      tip: "진자가 아래에 있으면 0, 수평이면 50, 직립이면 100인 숫자입니다. 각도가 아니라 높이 비율입니다. 예: ‘점수에 [진자 높이]만큼 더하기’에 연결하세요.",
      read: function (v) { return 50 * (1 + Math.cos(v.phi)); } },
    pvel: { cat: "kit", shape: "val", tpl: ["진자 빠르기 (0~100)"], group: "크기로 보기 · 0~100",
      tip: "진자 각속도의 크기 / 25 rad/s × 100을 0~100으로 제한한 숫자입니다. 방향을 구분하지 않습니다. 25 rad/s는 현재 시뮬레이션 속도 한계와 같으며, 100이 실물 안전을 보장하는 값은 아닙니다. 예: 빠르기에 0.2를 곱해 감점하세요.",
      read: function (v) { return clamp100(Math.abs(v.ald) / PEND_SPEED_MAX * 100); } },
    avel: { cat: "kit", shape: "val", tpl: ["팔 빠르기 (0~100)"], group: "크기로 보기 · 0~100",
      tip: "팔 각속도의 크기 / 19.2 rad/s × 100을 0~100으로 제한한 숫자입니다. 방향을 구분하지 않습니다. 19.2는 표시 기준이며 모델의 종료 한계 약 19.1986 rad/s와 조금 다릅니다. 예: ‘팔 빠르기 < 20’ 조건에 연결하세요.",
      read: function (v) { return clamp100(Math.abs(v.thd) / ARM_SPEED_MAX * 100); } },
    force: { cat: "kit", shape: "val", tpl: ["모터 힘 지령 (0~100)"], group: "크기로 보기 · 0~100",
      tip: "모터 명령 u의 절댓값 × 100입니다. 0은 영 지령, 100은 최대 크기의 지령이며 방향을 구분하지 않습니다. 실제 측정 토크나 소비 전력은 아닙니다. 예: 힘 지령에 0.5를 곱해 점수에서 빼세요.",
      read: function (v) { return clamp100(Math.abs(v.u) * 100); } },
    tilt: { cat: "kit", shape: "val", tpl: ["진자 기울기 (도)"], group: "크기로 보기 · 각도(도)",
      tip: "직립 오차의 절댓값입니다. 직립 0°, 수평 90°, 아래 180°이며 기울어진 방향은 구분하지 않습니다. 예: ‘진자 기울기 ≤ 10’에 연결하세요. 높이의 0~100 값과 단위가 다릅니다.",
      read: function (v) { return Math.abs(v.phi) * DEG; } },
    armang: { cat: "kit", shape: "val", tpl: ["팔 각도 크기 (도)"], group: "크기로 보기 · 각도(도)",
      tip: "시작 위치에서 돌아간 누적 팔 각도의 절댓값입니다. 한 바퀴는 360°, 두 바퀴는 720°이며 360에서 다시 0이 되지 않습니다. 예: 각도에 0.05를 곱해 감점하세요. 총 이동 거리와는 다릅니다.",
      read: function (v) { return Math.abs(v.th) * DEG; } },
    upright: { cat: "kit", shape: "bool", tpl: ["진자가 똑바로 섰는가?"], group: "상태를 참·거짓으로 보기",
      tip: "직립 오차 크기가 0.1745 rad(약 10°) 미만이고 진자 각속도 크기가 2 rad/s 미만이면 참입니다. 둘 다 만족해야 합니다. 예: ‘만일 [똑바로 섰는가?]라면’ 안에 보너스 점수를 넣으세요.",
      test: function (v) { return Math.abs(v.phi) < 0.1745 && Math.abs(v.ald) < 2; } },
    home: { cat: "kit", shape: "bool", tpl: ["팔이 제자리에 있는가?"], group: "상태를 참·거짓으로 보기",
      tip: "누적 팔 각도의 크기가 30° 미만이면 참입니다. 속도는 이 조건에서 확인하지 않습니다. 예: ‘그리고’로 진자 직립 조건과 함께 연결하세요.",
      test: function (v) { return Math.abs(v.th) * DEG < 30; } },

    tilt_signed: { cat: "kit", shape: "val", tpl: ["진자 직립 오차 ± (도)"], group: "고급 · 방향까지 보기",
      tip: "직립을 0으로 한 부호 있는 오차 φ를 도로 바꾼 숫자입니다. 양수와 음수는 모델 좌표계의 서로 반대 방향이며 화면의 좌우나 모터 방향과 바로 같다고 볼 수 없습니다. 약 −180~180°이며 아래를 지날 때 부호가 바뀔 수 있습니다. 예: −10~10 구간 판단에 연결하세요.",
      read: function (v) { return v.phi * DEG; } },
    armang_signed: { cat: "kit", shape: "val", tpl: ["팔 누적 각도 ± (도)"], group: "고급 · 방향까지 보기",
      tip: "시작 위치를 0으로 한 부호 있는 누적 팔 각도 θ입니다. 한 방향으로 한 바퀴는 +360°, 반대는 −360°이며 회전수를 보존합니다. 예: ‘팔 누적 각도 > 0’으로 방향에 따라 점수 규칙을 나눠 보세요.",
      read: function (v) { return v.th * DEG; } },
    pvel_signed: { cat: "kit", shape: "val", tpl: ["진자 각속도 ± (rad/s)"], group: "고급 · 방향까지 보기",
      tip: "부호 있는 진자 각속도 α̇입니다. 양수는 진자 좌표가 증가하는 방향, 음수는 감소하는 방향입니다. 0~100 빠르기와 단위가 다릅니다. 예: 절댓값을 취해 2 rad/s 미만인지 비교하세요.",
      read: function (v) { return v.ald; } },
    avel_signed: { cat: "kit", shape: "val", tpl: ["팔 각속도 ± (rad/s)"], group: "고급 · 방향까지 보기",
      tip: "부호 있는 팔 각속도 θ̇입니다. 팔 좌표가 증가하면 양수, 감소하면 음수입니다. 0~100 빠르기와 단위가 다릅니다. 예: ‘팔 각속도 × 팔 각속도’로 방향에 관계없이 빠른 움직임을 감점할 수 있습니다.",
      read: function (v) { return v.thd; } },

    /* ── 계산 ── */
    add: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "+", { s: "num", v: 10 }], fn: function (a, b) { return a + b; },
      tip: "두 숫자를 더해 숫자로 내보냅니다. 예: 높이 + 10을 점수 칸에 넣으세요. 서로 다른 단위를 더할 때는 어떤 의미의 점수인지 먼저 정하세요." },
    sub: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "-", { s: "num", v: 10 }], fn: function (a, b) { return a - b; },
      tip: "왼쪽 숫자에서 오른쪽 숫자를 뺍니다. 순서를 바꾸면 부호가 달라집니다. 예: 100 − 높이를 쓰면 아래에 있을수록 큰 값입니다." },
    mul: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "x", { s: "num", v: 0.5 }], fn: function (a, b) { return a * b; },
      tip: "두 숫자를 곱합니다. 0.5를 곱하면 절반, 0이면 항상 0, 음수를 곱하면 부호가 바뀝니다. 예: 힘 지령 × 0.5를 감점 칸에 넣으세요." },
    div: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "/", { s: "num", v: 2 }],
      fn: function (a, b) { return b === 0 ? 0 : a / b; },
      tip: "왼쪽을 오른쪽으로 나눈 숫자입니다. 나누는 수는 0이면 안 됩니다. 예: 높이 / 100으로 0~1 범위로 바꾸세요. 변하는 값을 분모로 쓰면 0에 닿는지 확인하세요." },
    pow: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "의", { dd: "op", opts: [["sq", "제곱"], ["abs", "절댓값"]] }],
      fn: function (a, f) { return f.op === "abs" ? Math.abs(a) : a * a; },
      tip: "제곱은 값 × 값, 절댓값은 방향을 없앤 크기입니다. 예: (진자 각속도)의 절댓값 < 2. 제곱은 큰 값을 더 크게 만들므로 감점 배율도 함께 살펴보세요." },
    min: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "와", { s: "num", v: 20 }, "중 작은 값"],
      fn: function (a, b) { return Math.min(a, b); },
      tip: "두 숫자 중 작은 숫자를 내보냅니다. 예: 높이와 80 중 작은 값을 점수에 넣으면 높이 점수가 80을 넘지 않습니다." },
    max: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 10 }, "와", { s: "num", v: 20 }, "중 큰 값"],
      fn: function (a, b) { return Math.max(a, b); },
      tip: "두 숫자 중 큰 숫자를 내보냅니다. 예: (높이 − 50)와 0 중 큰 값을 쓰면 수평을 넘은 높이만 점수로 줄 수 있습니다." },
    clamp: { cat: "calc", shape: "val", tpl: [{ s: "num", v: 50 }, "을", { s: "num", v: 0 }, "이상", { s: "num", v: 100 }, "이하로 제한"],
      fn: function (x, lo, hi) { return Math.min(hi, Math.max(lo, x)); },
      tip: "첫 숫자를 최솟값~최댓값 안으로 제한해 내보냅니다. 범위 안이면 그대로, 밖이면 가까운 끝값을 씁니다. 예: 점수 계산값을 −100~100으로 제한하세요. 최솟값이 최댓값보다 크면 순서를 고쳐야 합니다." },

    /* ── 판단 ── */
    lt: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 0 }, "<", { s: "num", v: 10 }], fn: function (a, b) { return a < b; },
      tip: "왼쪽 숫자가 오른쪽보다 작을 때 참입니다. 같으면 거짓입니다. 예: 진자 기울기 < 10. 양쪽 숫자의 단위를 맞추세요." },
    gt: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 0 }, ">", { s: "num", v: 10 }], fn: function (a, b) { return a > b; },
      tip: "왼쪽 숫자가 오른쪽보다 클 때 참입니다. 같으면 거짓입니다. 예: 높이 > 80. 양쪽 숫자의 단위를 맞추세요." },
    le: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 0 }, "≤", { s: "num", v: 10 }], fn: function (a, b) { return a <= b; },
      tip: "왼쪽이 오른쪽보다 작거나 같으면 참입니다. 10 ≤ 10도 참입니다. 예: 진자 기울기 ≤ 10으로 ‘10도 이하’를 표현하세요." },
    ge: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 100 }, "≥", { s: "num", v: 80 }], fn: function (a, b) { return a >= b; },
      tip: "왼쪽이 오른쪽보다 크거나 같으면 참입니다. 80 ≥ 80도 참입니다. 예: 높이 ≥ 80으로 경계값까지 포함하세요." },
    eq: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 10 }, "=", { s: "num", v: 10 }], fn: function (a, b) { return a === b; },
      tip: "두 숫자가 정확히 같을 때 참입니다. 센서값이나 소수 계산은 조금씩 달라 정확히 같기 어렵습니다. 예: 10 = 10은 참. 직립 근처를 판단할 때는 ‘기울기 ≤ 10’처럼 범위 조건을 권합니다." },
    neq: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 10 }, "≠", { s: "num", v: 20 }], fn: function (a, b) { return a !== b; },
      tip: "두 숫자가 정확히 같지 않으면 참입니다. 아주 작은 차이도 다르다고 판단합니다. 예: 10 ≠ 20은 참입니다. 숫자 값을 바꾸는 대입 명령은 아닙니다." },
    between: { cat: "judge", shape: "bool", tpl: [{ s: "num", v: 50 }, "이", { s: "num", v: 0 }, "이상", { s: "num", v: 100 }, "이하인가?"],
      fn: function (x, lo, hi) { return lo <= x && x <= hi; },
      tip: "첫 숫자가 최솟값 이상이고 최댓값 이하이면 참입니다. 양 끝도 포함합니다. 예: 진자 직립 오차가 −10~10°인지 판단하세요. 최솟값이 최댓값보다 크면 순서를 고쳐야 합니다." },
    and: { cat: "judge", shape: "bool", tpl: [{ s: "bool" }, "그리고", { s: "bool" }], fnb: function (a, b) { return a && b; },
      tip: "두 육각형 조건이 모두 참일 때만 참입니다. 예: ‘진자가 똑바로 섰는가?’ 그리고 ‘팔이 제자리에 있는가?’. 숫자 대신 판단 블록을 양쪽에 넣으세요." },
    or: { cat: "judge", shape: "bool", tpl: [{ s: "bool" }, "또는", { s: "bool" }], fnb: function (a, b) { return a || b; },
      tip: "두 조건 중 하나 이상이 참이면 참입니다. 둘 다 참이어도 참입니다. 예: ‘팔 빠르기 > 80’ 또는 ‘진자 빠르기 > 80’이면 감점하기. 이는 점수 규칙이며 실제 정지 명령은 아닙니다." },
    not: { cat: "judge", shape: "bool", tpl: [{ s: "bool" }, "(이)가 아니다"], fnb: function (a) { return !a; },
      tip: "육각형 조건의 참과 거짓을 뒤집습니다. 예: ‘팔이 제자리에 있는가?’가 아니다 → 팔 각도 크기가 30° 이상일 때 참입니다. 빈칸은 조건을 뜻하지 않으므로 판단 블록을 연결하세요." },
    "true": { cat: "judge", shape: "bool", tpl: ["참"], constant: true, literal: true, test: function () { return true; },
      tip: "항상 참인 판단값입니다. 예: ‘만일 참이라면’으로 안쪽 점수 블록이 실행되는지 살펴보세요. 최종 규칙에서는 키트 상태 조건으로 바꿔 보세요." },
    "false": { cat: "judge", shape: "bool", tpl: ["거짓"], constant: true, literal: false, test: function () { return false; },
      tip: "항상 거짓인 판단값입니다. 예: ‘만일 거짓이라면 / 아니면’에서 아니면 쪽을 확인하세요. 참·거짓 블록은 숫자 칸에 들어가지 않습니다." },

    /* ── 흐름 ── */
    "if": { cat: "flow", shape: "c", dom: "reward", bodies: 1, tpl: ["만일", { s: "bool" }, "(이)라면"],
      tip: "육각형 조건이 참인 순간에만 안쪽 점수 블록을 실행합니다. 거짓이면 건너뜁니다. 예: 직립 조건 안에 50점 더하기를 넣으세요. 한 번만 실행하는 명령이 아니라 점수를 매기는 매 순간 확인합니다." },
    ifelse: { cat: "flow", shape: "c", dom: "reward", bodies: 2, mid: "아니면", tpl: ["만일", { s: "bool" }, "(이)라면"],
      tip: "조건이 참이면 위쪽, 거짓이면 ‘아니면’ 아래쪽을 실행합니다. 한 순간에 한 쪽만 실행합니다. 예: 기울기 ≤ 10이면 보너스, 아니면 기울기만큼 감점하기. 안에는 점수나 다른 조건 블록을 넣으세요." },

    /* ── 점수 ── */
    plus: { cat: "score", shape: "stk", dom: "reward", tpl: ["점수에", { s: "num", v: 10 }, "만큼 더하기"],
      tip: "숫자 칸의 값을 이 순간 점수에 더합니다. 양수는 보상, 음수를 더하면 감점입니다. 예: 진자 높이를 넣으면 높을수록 점수가 커집니다. 여러 점수 블록은 합산됩니다." },
    minus: { cat: "score", shape: "stk", dom: "reward", tpl: ["점수에서", { s: "num", v: 10 }, "만큼 빼기"],
      tip: "숫자 칸의 값을 이 순간 점수에서 뺍니다. 양수를 빼면 감점, 음수를 빼면 보상이 됩니다. 예: 힘 지령 × 0.5를 넣으세요. 매 순간의 점수는 새로 계산되며 에피소드 보상은 그 점수들을 누적합니다." },

    /* ── 따라 하기 (고르기만 하는 블록, 미리 학습한 아홉 정책과 짝) ── */
    g_up: { cat: "score", shape: "stk", dom: "guide", tpl: ["진자가 설수록 점수 주기"],
      tip: "따라 하기에서 고정된 직립 목표입니다. 직립 오차가 작고 천천히 설수록 유리한 기본 점수식을 사용합니다. 자유롭게 만들기의 ‘높이만 더하기’와 완전히 같은 식은 아닙니다." },
    g_smooth: { cat: "score", shape: "stk", dom: "guide", tpl: ["진자를 빠르게 휘두르면", { dd: "lv", opts: LEVELS }],
      tip: "진자 각속도의 제곱에 대한 감점 중요도를 고릅니다. 없음·약하게·강하게 중 선택합니다. 강하게 고르면 휘둘러 올라가는 움직임도 손해를 볼 수 있으니 결과를 비교하세요." },
    g_effort: { cat: "score", shape: "stk", dom: "guide", tpl: ["모터를 세게 쓰면", { dd: "lv", opts: LEVELS }],
      tip: "모터 명령의 제곱에 대한 감점 중요도를 고릅니다. 없음·약하게·강하게 중 선택합니다. 전기 소비량을 직접 측정하는 블록은 아닙니다. 힘을 덜 쓰는 것과 잘 세우는 것의 절충을 살펴보세요." },

    /* ── 인공지능 ── */
    cond: { cat: "ai", shape: "stk", dom: "run",
      tpl: ["학습 조건", { dd: "key", opts: [["gens", "세대"], ["pop", "한 세대에 해 볼 수"], ["sigma", "바꾸는 크기"]] },
        "을(를)", { s: "num", v: 24 }, "(으)로 바꾸기"],
      tip: "학습할 때 사용할 숫자 조건입니다. 세대 4~80(정수), 한 세대에 해 볼 정책 수 6~40(정수), 바꾸는 크기 1~30(입력값/100을 사용)입니다. 키트의 현재 상태가 아니라 일정한 숫자를 넣으세요. 조건 종류를 바꾼 뒤 범위도 확인하세요." },
    learn: { cat: "ai", shape: "stk", dom: "run", tpl: ["내 점수 규칙으로 정책 학습하기"],
      tip: "현재 점수 규칙과 학습 조건으로 정책을 고쳐 배웁니다. 처음부터 무작위로 배우는 대신 미리 배운 정책에서 출발합니다. 예: 시작하기 묶음에서 학습 조건 뒤에 놓으세요. 점수를 높였다고 반드시 실제 진자가 잘 서는 것은 아닙니다." },
    test: { cat: "ai", shape: "stk", dom: "run", tpl: [{ s: "num", v: 10 }, "초 동안 시험하기"],
      tip: "정책을 3~20초(정수) 동안 시험합니다. 숫자는 실행 시간이며 학습 횟수가 아닙니다. 예: 학습하기 뒤에 10초 시험을 놓으세요. PC 시뮬레이션인지 실제 키트인지는 시작하기 옆의 실행 환경을 확인하세요." }
  };

  /* UI/diagnostics metadata only. Existing block identifiers and slot structures stay compatible. */
  var INFO = {
    height: ["진자 높이", "높다 낮다 서다 매달리다 비율 height", "0~100", [0, 100]],
    pvel: ["진자 빠르기", "속도 진동 부드럽게 느리게 pendulum speed", "0~100", [0, 100]],
    avel: ["팔 빠르기", "속도 회전 부드럽게 느리게 arm speed", "0~100", [0, 100]],
    force: ["모터 힘 지령", "입력 행동 토크 전류 명령 힘아끼기 effort action", "0~100", [0, 100]],
    tilt: ["진자 기울기", "직립 각도 오차 도 angle tilt", "deg", [0, 180]],
    armang: ["팔 각도 크기", "회전 누적 시작 위치 절댓값 arm angle", "deg"],
    tilt_signed: ["진자 직립 오차 · 방향 포함", "고급 부호 방향 양수 음수 phi signed", "deg", [-180, 180]],
    armang_signed: ["팔 누적 각도 · 방향 포함", "고급 부호 방향 양수 음수 theta signed", "deg"],
    pvel_signed: ["진자 각속도 · 방향 포함", "고급 부호 양수 음수 속도 rad/s alphaDot signed", "rad/s"],
    avel_signed: ["팔 각속도 · 방향 포함", "고급 부호 양수 음수 속도 rad/s thetaDot signed", "rad/s"],
    upright: ["진자가 똑바로 섰는가?", "직립 균형 서기 보너스 upright"],
    home: ["팔이 제자리에 있는가?", "시작 위치 각도 30 home"],
    add: ["덧셈", "더하기 합 합계 + add"], sub: ["뺄셈", "빼기 차이 - subtract"],
    mul: ["곱셈", "곱하기 배율 가중치 x × multiply"], div: ["나눗셈", "나누기 정규화 비율 / ÷ divide"],
    pow: ["제곱 · 절댓값", "음수 크기 방향 square absolute abs"],
    min: ["작은 값", "최솟값 둘중 최소 min"], max: ["큰 값", "최댓값 둘중 최대 max"],
    clamp: ["범위로 제한", "최소 최대 상한 하한 자르기 포화 clamp clip"],
    lt: ["작다", "미만 비교 < less"], gt: ["크다", "초과 비교 > greater"],
    le: ["작거나 같다", "이하 경계 포함 비교 <= ≤"], ge: ["크거나 같다", "이상 경계 포함 비교 >= ≥"],
    eq: ["같다", "정확히 같음 비교 = equal"], neq: ["다르다", "같지않다 불일치 != ≠ not equal"],
    between: ["범위 안인가?", "구간 사이 이상 이하 최소 최대 경계 포함 range between"],
    and: ["그리고", "모두 둘다 조건 and"], or: ["또는", "하나이상 둘중 조건 or"],
    not: ["아니다", "반대 뒤집기 부정 조건 not"],
    "true": ["참", "항상 실행 true"], "false": ["거짓", "항상 건너뛰기 false"],
    "if": ["만일 조건이라면", "조건 흐름 보너스 if"], ifelse: ["만일 / 아니면", "조건 분기 두가지 if else"],
    plus: ["점수 더하기", "보상 칭찬 가점 reward score +"], minus: ["점수 빼기", "감점 벌점 패널티 penalty score -"],
    g_up: ["진자가 설수록 점수 주기", "따라하기 직립"], g_smooth: ["진자 빠르기 감점", "따라하기 부드럽게"], g_effort: ["힘 사용 감점", "따라하기 힘아끼기"],
    cond: ["학습 조건 바꾸기", "세대 횟수 정책 수 바꾸는 크기 gens pop sigma"],
    learn: ["내 점수 규칙으로 학습", "가르치기 정책 학습 시작 learn train"],
    test: ["정책 시험하기", "실행 초 시간 테스트 시뮬레이션 test run"]
  };
  Object.keys(DEFS).forEach(function (key) {
    var d = DEFS[key], info = INFO[key];
    d.name = info[0];
    d.search = d.name + " " + info[1] + " " + key;
    d.unit = info[2] || (d.shape === "bool" ? "boolean" : d.shape === "val" ? "number" : "statement");
    if (info[3]) d.range = info[3];
    if (key.indexOf("_signed") >= 0) d.advanced = true;
    if (d.cat === "judge") d.group = ["and", "or", "not"].indexOf(key) >= 0 ? "조건을 연결하기" : ["true", "false"].indexOf(key) >= 0 ? "참·거짓으로 흐름 확인하기" : "숫자를 비교하기";
    if (d.cat === "calc") d.group = ["min", "max", "clamp"].indexOf(key) >= 0 ? "크기와 범위 정하기" : "숫자 계산하기";
  });

  var RUN_PARAMS = {
    gens: { name: "세대", min: 4, max: 80, defaultValue: 24, integer: true, unit: "세대", scale: 1 },
    pop: { name: "한 세대에 해 볼 정책 수", min: 6, max: 40, defaultValue: 20, integer: true, unit: "개", scale: 1 },
    sigma: { name: "바꾸는 크기", min: 1, max: 30, defaultValue: 6, integer: false, unit: "입력 단위", scale: 0.01 }
  };
  var TEST_PARAM = { name: "시험 시간", min: 3, max: 20, defaultValue: 10, integer: true, unit: "초", scale: 1 };
  function numericSpec(type, fields, slotIndex) {
    if (slotIndex !== 0) return null;
    if (type === "cond") return RUN_PARAMS[fields && fields.key] || RUN_PARAMS.gens;
    return type === "test" ? TEST_PARAM : null;
  }

  var HATS = {
    reward: { cat: "score", glyph: "★", label: "매 순간 점수 매기기",
      tip: "제어 주기 0.02초마다 이 아래 점수·조건 블록으로 이번 순간의 점수를 새로 계산합니다. 점수 블록의 결과를 더해 순간 보상을 만들고, 에피소드에서는 순간 보상을 누적합니다. 학습하기·시험하기 블록은 다른 시작 묶음에 놓으세요." },
    run: { cat: "start", glyph: "▶", label: "시작하기 버튼을 클릭했을 때",
      tip: "시작하기 버튼에 사용할 학습 조건·학습 여부·시험 시간을 정하는 묶음입니다. 점수 공식은 ‘매 순간 점수 매기기’에 놓으세요. 조건을 정하고 학습하기, 시험하기 순서로 구성하면 읽기 쉽습니다." }
  };

  var PALETTE = {
    start: [],
    flow: ["if", "ifelse"],
    judge: ["lt", "le", "gt", "ge", "eq", "neq", "between", "and", "or", "not", "true", "false"],
    calc: ["add", "sub", "mul", "div", "pow", "min", "max", "clamp"],
    score: ["plus", "minus"],
    kit: ["height", "pvel", "avel", "force", "tilt", "armang", "upright", "home", "tilt_signed", "armang_signed", "pvel_signed", "avel_signed"],
    ai: ["cond", "learn", "test"]
  };

  /* 범주 아이콘 (20x20, 색은 currentColor). 글자 기호는 글꼴에 따라 깨지므로 그림으로 그립니다. */
  var ICONS = {
    start: '<path d="M7 4.2v11.6l9.4-5.8z" fill="currentColor"/>',
    flow: '<path d="M14.6 6.6A5.6 5.6 0 1 0 15.6 11" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/><path d="M16.4 2.8v4.6h-4.6z" fill="currentColor"/>',
    judge: '<path d="M4.4 10.6l3.6 3.6 7.6-8.2" fill="none" stroke="currentColor" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>',
    calc: '<path d="M10 4.4v11.2M4.4 10h11.2" fill="none" stroke="currentColor" stroke-width="2.7" stroke-linecap="round"/>',
    score: '<path d="M10 2.6l2.3 4.7 5.1.7-3.7 3.6.9 5.1-4.6-2.4-4.6 2.4.9-5.1L2.6 8l5.1-.7z" fill="currentColor"/>',
    kit: '<rect x="4" y="14.2" width="12" height="3" rx="1.5" fill="currentColor"/><path d="M10 14V7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/><circle cx="10" cy="4.9" r="2.7" fill="currentColor"/>',
    ai: '<text x="10" y="13.8" font-size="9.5" font-weight="800" text-anchor="middle" fill="currentColor" font-family="Arial, sans-serif">AI</text>'
  };
  function iconSvg(key) {
    return '<svg viewBox="0 0 20 20" width="100%" height="100%" aria-hidden="true">' + (ICONS[key] || "") + "</svg>";
  }

  function catOf(key) {
    for (var i = 0; i < CATS.length; i++) if (CATS[i].key === key) return CATS[i];
    return CATS[0];
  }

  PS.CATS = CATS;
  PS.DEFS = DEFS;
  PS.HATS = HATS;
  PS.PALETTE = PALETTE;
  PS.RUN_PARAMS = RUN_PARAMS;
  PS.numericSpec = numericSpec;
  PS.catOf = catOf;
  PS.iconSvg = iconSvg;
  PS.blockColor = function (type) { return catOf(DEFS[type].cat).color; };
})(window.PS = window.PS || {});
