/* 예시 규칙. 학생이 블록으로 쌓을 만한 점수 규칙을 짧은 표기로 적어 둔 것입니다.
 *   숫자 또는 { t: 블록 종류, a: [칸...], f: { 고르는 칸 }, body: [[안쪽 블록...]] }
 * 앱의 '예시 규칙' 탭과 검증 스크립트(s2r/check_app_learning.js)가 같이 씁니다.
 *   hard: true  될지 모르는 규칙 (학습지의 "아주 강하게 하면?")
 *   bad: true   일부러 틀린 규칙 (규칙 점검과 안전 시험이 걸러내는지 보는 용도)
 */
(function (PS) {
  "use strict";

  var H = { t: "height" };
  PS.EXAMPLES = [
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
