/* 예시 규칙. 학생이 블록으로 쌓을 만한 점수 규칙을 짧은 표기로 적어 둔 것입니다.
 *   숫자 또는 { t: 블록 종류, a: [칸...], f: { 고르는 칸 }, body: [[안쪽 블록...]] }
 * 앱의 '예시 규칙' 탭과 검증 스크립트(s2r/check_app_learning.js)가 같이 씁니다.
 *   hard: true  될지 모르는 규칙 (학습지의 "아주 강하게 하면?")
 *   bad: true   일부러 틀린 규칙 (규칙 점검과 안전 시험이 걸러내는지 보는 용도)
 */
(function (PS) {
  "use strict";

  var H = { t: "height" };
  var get = function (key) { return { t: 'get_var', f: { variable: key } }; };
  var set = function (key, value) { return { t: 'set_var', f: { variable: key }, a: [value] }; };
  var op = function (type, a, b) { return { t: type, a: [a, b] }; };
  var sq = function (a) { return { t: 'pow', a: [a], f: { op: 'sq' } }; };
  var abs = function (a) { return { t: 'pow', a: [a], f: { op: 'abs' } }; };
  var exp = function (a) { return { t: 'math', a: [a], f: { op: 'exp' } }; };
  var phi = { t: 'tilt_rad' }, w = { t: 'pvel_signed' }, v = { t: 'avel_signed' }, u = { t: 'action_signed' };
  function appReward(ws, we) {
    return [set('A', op('sub', 1, op('mul', 0.3, sq(phi)))),
      set('B', op('add', op('mul', ws, sq(w)), op('mul', 0.002, sq(v)))),
      set('C', op('mul', we, sq(u))),
      set('D', op('mul', 0.5, op('mul', exp(op('mul', -11.111111, sq(phi))), exp(op('mul', -0.25, sq(w)))))),
      { t: 'plus', a: [get('A')] }, { t: 'minus', a: [get('B')] }, { t: 'minus', a: [get('C')] }, { t: 'plus', a: [get('D')] }];
  }
  var repo = 'https://github.com/seonghwan0722/furuta-education-platform/blob/main/';
  var realApp = { name: '우리 앱의 실제 보상 · 약하게 / 약하게',
    why: '현재 따라 하기 기본 선택과 같은 순간 보상입니다. A 직립 목표, B 속도 감점, C 지령 감점, D 직립 근처 보너스로 나눴습니다. 단위는 rad·rad/s·정규화 지령입니다. 블록으로 불러오면 자유롭게 만들기의 CEM 학습을 사용하며, 기존 SAC 정책을 그대로 재현하는 것은 아닙니다.',
    formula: 'r = 1 − 0.3φ² − 0.002ω² − 0.002v² − 0.02u²\n    + 0.5 exp(−11.111111φ²) exp(−0.25ω²)\nφ: 진자 직립 오차(rad), ω: 진자 속도, v: 팔 속도(rad/s), u: 지령(−1~1)\n정지 직립: 1.5점 · 정지 매달림: 약 −1.961점',
    sources: [{ label: '앱 보상 원본 · reward.basic', url: repo + 'pendulum_studio/src/js/reward.js' }],
    variables: { A: '직립 목표', B: '속도 감점', C: '지령 감점', D: '직립 보너스' }, nodes: appReward(0.002, 0.02) };
  var realStrong = { name: '우리 앱의 실제 보상 · 강하게 / 강하게',
    why: '따라 하기의 빠르기·힘 감점을 모두 강하게 선택한 보상입니다. 약하게 예제에서 B의 진자 속도 계수는 0.002→0.008, C의 지령 계수는 0.02→0.10으로 바뀝니다. 어떤 움직임이 더 불리해질지 비교해 보세요.',
    formula: 'r = 1 − 0.3φ² − 0.008ω² − 0.002v² − 0.10u²\n    + 0.5 exp(−11.111111φ²) exp(−0.25ω²)', sources: realApp.sources,
    variables: realApp.variables, nodes: appReward(0.008, 0.10) };
  var rev22 = { name: '우리 rev22 PPO·SAC · 상태 보상 항 살펴보기',
    why: 'rev22 PPO rwdef와 SAC가 공통으로 쓰는 상태 보상 항을 조립했습니다. 원래 학습에는 추가로 −2×회생량, −0.05×직전 지령과의 차이², 종료 벌점(PPO −300 / SAC −100)이 있습니다. 이 예제에는 그 항이 없으며 앱의 rev11 환경에서 상태 항을 비교하는 학습용 예제입니다. 전체 rev22 학습 보상·실물 정책을 재현하지 않습니다.',
    formula: 'n = exp(−(φ/0.15)²)\nr상태 = (1+cosφ)/2 + n exp(−ω²) − 0.02u²\n    − 0.15 max(0, |v|−9)² − 0.05nθ² − 0.2nv² − 0.05nω²\n    + 3 × [|φ|≤5° 그리고 |ω|≤0.5 rad/s]\nθ: −π~π로 감싼 팔 각도(rad) · 정지 직립: 5점\n원 학습: 100 Hz·1.5 A / 이 예제 실행: 현재 앱의 50 Hz·1.2 A',
    sources: [{ label: '공통 상태 보상 함수', url: repo + 'python_handoff/train_bench_torch.py' }, { label: 'rev22 보상 수정·학습 코드', url: repo + 'rev22_control/rl/code/train_rev22.py' }],
    variables: { A: '직립 근접도', B: '높이 점수', C: '변수 C', D: '변수 D' },
    nodes: [set('A', exp(op('mul', -1, sq(op('div', phi, 0.15))))), set('B', op('div', H, 100)),
      { t: 'plus', a: [get('B')] }, { t: 'plus', a: [op('mul', get('A'), exp(op('mul', -1, sq(w))))] },
      { t: 'minus', a: [op('mul', 0.02, sq(u))] },
      { t: 'minus', a: [op('mul', 0.15, sq(op('max', 0, op('sub', abs(v), 9))))] },
      { t: 'minus', a: [op('mul', 0.05, op('mul', get('A'), sq({ t: 'arm_rad' })))] },
      { t: 'minus', a: [op('mul', 0.2, op('mul', get('A'), sq(v)))] },
      { t: 'minus', a: [op('mul', 0.05, op('mul', get('A'), sq(w)))] },
      { t: 'if', a: [op('and', op('le', abs(phi), Math.PI / 36), op('le', abs(w), 0.5))], body: [[{ t: 'plus', a: [3] }]] }] };
  PS.EXAMPLES = [
    realApp, realStrong, rev22,
    { name: '변수와 반복 · 높이 구간 보너스',
      why: 'A에 20부터 시작하는 높이 경계를 담고 4번 반복합니다. 높이가 20·40·60·80 이상일 때마다 B에 10을 더해 마지막에 점수로 줍니다. 직립에서는 높이 100 + 보너스 40 = 140점입니다. 반복 횟수는 진자의 시험 횟수가 아닙니다.',
      variables: { A: '높이 경계', B: '보너스 합계', C: '변수 C', D: '변수 D' },
      nodes: [set('A', 20), set('B', 0), { t: 'repeat', a: [4], body: [[
        { t: 'if', a: [op('ge', H, get('A'))], body: [[{ t: 'change_var', f: { variable: 'B' }, a: [10] }]] },
        { t: 'change_var', f: { variable: 'A' }, a: [20] }]] }, { t: 'plus', a: [H] }, { t: 'plus', a: [get('B')] }] },
    { name: '반복 번호와 조건 · 가까운 구간 찾기',
      why: '직립 오차가 5·10·15·20° 중 처음 들어맞는 구간을 찾습니다. 맞지 않으면 이번 반복을 건너뛰고, 맞으면 보너스를 더한 뒤 반복을 중단합니다. 안쪽 중단·건너뛰기는 모터 정지 명령이 아닙니다.',
      nodes: [{ t: 'plus', a: [H] }, { t: 'repeat', a: [4], body: [[
        { t: 'if', a: [op('gt', { t: 'tilt' }, op('mul', { t: 'loop_index' }, 5))], body: [[{ t: 'continue_loop' }]] },
        { t: 'plus', a: [op('sub', 50, op('mul', { t: 'loop_index' }, 10))] }, { t: 'break_loop' }]] }] },
    { name: "높이만", why: "진자가 높이 올라갈수록 점수를 줍니다.", nodes: [{ t: "plus", a: [H] }] },
    { name: "섰으면 100점", why: "서 있을 때만 점수를 줍니다. 올라가는 중에는 점수가 없습니다.",
      nodes: [{ t: "if", a: [{ t: "upright" }], body: [[{ t: "plus", a: [100] }]] }] },
    { name: "기울면 감점", why: "똑바로에서 기운 만큼 점수를 깎습니다. 점수가 늘 0 이하입니다.",
      nodes: [{ t: "minus", a: [{ t: "tilt" }] }] },
    { name: "높이 + 서면 보너스", why: "올라가는 것도 칭찬하고, 서면 크게 칭찬합니다.",
      nodes: [{ t: "plus", a: [H] }, { t: "if", a: [{ t: "upright" }], body: [[{ t: "plus", a: [50] }]] }] },
    { name: "힘 아끼기", why: "세우되 모터를 덜 쓰게 합니다. 서 있을 때 모터 힘이 줄어드는지 보세요.",
      nodes: [{ t: "plus", a: [H] }, { t: "minus", a: [{ t: "mul", a: [{ t: "force" }, 0.5] }] }] },
    { name: "팔 제자리", why: "팔이 처음 자리에서 멀리 가지 않게 합니다. 팔이 돌아간 정도를 보세요.",
      nodes: [{ t: "plus", a: [H] }, { t: "minus", a: [{ t: "mul", a: [{ t: "armang" }, 0.05] }] }] },
    { name: "팔 천천히", why: "팔이 덜 휘둘리게 합니다.",
      nodes: [{ t: "plus", a: [H] }, { t: "minus", a: [{ t: "mul", a: [{ t: "avel" }, 0.5] }] }] },
    { name: "조용히 서기", why: "서 있을 때만 점수를 주고, 모터 힘은 늘 감점합니다.",
      nodes: [{ t: "if", a: [{ t: "upright" }], body: [[{ t: "plus", a: [100] }]] }, { t: "minus", a: [{ t: "mul", a: [{ t: "force" }, 0.3] }] }] },
    { name: "전부 다", why: "생각나는 조건을 다 넣은 규칙입니다. 조건이 많으면 어떻게 될까요?",
      nodes: [{ t: "plus", a: [H] }, { t: "if", a: [{ t: "upright" }], body: [[{ t: "plus", a: [50] }]] },
        { t: "minus", a: [{ t: "mul", a: [{ t: "force" }, 0.3] }] }, { t: "minus", a: [{ t: "mul", a: [{ t: "pvel" }, 0.3] }] },
        { t: "minus", a: [{ t: "mul", a: [{ t: "armang" }, 0.1] }] }] },
    { name: "힘 아주 아끼기", hard: true, why: "힘 아끼기를 아주 강하게 하면 어떻게 될까요? (학습지 4쪽)",
      nodes: [{ t: "plus", a: [H] }, { t: "minus", a: [{ t: "mul", a: [{ t: "force" }, 2] }] }] },
    { name: "진자 천천히", hard: true, why: "진자가 휙휙 돌지 않게 합니다. 휘둘러 올리려면 빨라야 하는데 괜찮을까요?",
      nodes: [{ t: "plus", a: [H] }, { t: "minus", a: [{ t: "mul", a: [{ t: "pvel" }, 1] }] }] },
    { name: "왜 안 될까? 부호 반대", bad: true, why: "더하기 대신 빼기를 붙인 규칙입니다. 규칙 점검이 무엇이라고 하는지 보세요.",
      nodes: [{ t: "minus", a: [H] }] },
    { name: "왜 안 될까? 빨리 돌려라", bad: true, why: "진자가 빨리 돌수록 점수를 줍니다. 규칙 점검이 무엇이라고 하는지 보세요.",
      nodes: [{ t: "plus", a: [{ t: "pvel" }] }] },
    { name: "−10°부터 +10°까지", concepts: ["구간 판단", "아니면", "부호 있는 각도"],
      why: "높이에 점수를 주고, 직립 오차가 −10~10°이면 30점 보너스, 아니면 기울기만큼 조금 감점합니다. 경계값 ±10°도 포함합니다. 구간을 넓히면 무엇이 달라질지 예상해 보세요.",
      nodes: [{ t: "plus", a: [H] },
        { t: "ifelse", a: [{ t: "between", a: [{ t: "tilt_signed" }, -10, 10] }],
          body: [[{ t: "plus", a: [30] }], [{ t: "minus", a: [{ t: "mul", a: [{ t: "tilt" }, 0.1] }] }]] }] },
    { name: "둘 다 만족? 하나라도 빠르면?", concepts: ["그리고", "또는", "이상 비교"],
      why: "직립과 팔 제자리 조건을 둘 다 만족하면 보너스를 줍니다. 팔·진자 중 하나라도 빠르기 값이 80 이상이면 감점합니다. ‘그리고’와 ‘또는’를 바꾸면 어느 상태의 점수가 달라질까요? 이 조건은 점수만 바꾸며 정지 명령이 아닙니다.",
      nodes: [{ t: "plus", a: [H] },
        { t: "if", a: [{ t: "and", a: [{ t: "upright" }, { t: "home" }] }], body: [[{ t: "plus", a: [50] }]] },
        { t: "if", a: [{ t: "or", a: [{ t: "ge", a: [{ t: "pvel" }, 80] }, { t: "ge", a: [{ t: "avel" }, 80] }] }],
          body: [[{ t: "minus", a: [20] }]] }] },
    { name: "빠를수록 더 크게 감점하기", concepts: ["제곱", "가중치", "범위 제한"], hard: true,
      why: "높이에서 ‘진자 빠르기² × 0.005’를 빼고 점수를 −50~100으로 제한합니다. 빠르기 20일 때 감점은 2, 40이면 8입니다. 감점이 너무 강하면 휘둘러 올라가는 것까지 방해할 수 있으니 배율을 한 가지씩 바꿔 보세요.",
      nodes: [{ t: "plus", a: [{ t: "clamp", a: [
        { t: "sub", a: [H, { t: "mul", a: [{ t: "pow", a: [{ t: "pvel" }], f: { op: "sq" } }, 0.005] }] }, -50, 100
      ] }] }] }
  ];
})(window.PS = window.PS || {});
