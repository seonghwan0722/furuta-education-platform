/* 점수 규칙(보상).
 *
 * 보상 함수 서명은 어디서나 같습니다.
 *   fn(phi, alphaDot, thetaDot, u, theta) -> 점수        (phi = 똑바로 섰을 때 0)
 *
 * 따라 하기: 학습 때 쓴 환경(rl/train_rules.py)의 보상과 같은 식이고, 두 고르는 칸이 가중치를 정합니다.
 *   r = 1 − 0.3 φ² − w_smooth·α̇² − 0.002·θ̇² − w_effort·u² + 0.5·exp(−(φ/0.3)²)·exp(−(α̇/2)²)
 * 자유롭게 만들기: 학생이 쌓은 블록을 그대로 계산합니다.
 *
 * 블록 모델 (blocks.js 가 만듦)
 *   B[id] = { id, type, s: [{ block, v }], f: { 고르는 칸 }, bodies: [[id...], ...] }
 *   scripts.reward = [id...]   매 순간 점수 매기기 아래
 *   scripts.run    = [id...]   시작하기 버튼을 클릭했을 때 아래
 */
(function (PS) {
  "use strict";

  var WORD = ["없음", "약하게", "강하게"];
  var W_SMOOTH = [0, 0.002, 0.008];
  var W_EFFORT = [0, 0.02, 0.10];

  function basic(smooth, effort) {
    var ws = W_SMOOTH[smooth], we = W_EFFORT[effort];
    var text = "점수 = 세워짐";
    if (smooth) text += " − 빠르기(" + WORD[smooth] + ")";
    if (effort) text += " − 힘(" + WORD[effort] + ")";
    function fn(phi, ald, thd, u) {
      var near = Math.exp(-11.111111 * phi * phi);
      var slow = Math.exp(-0.25 * ald * ald);
      return 1 - 0.3 * phi * phi - ws * ald * ald - 0.002 * thd * thd
        - we * u * u + 0.5 * near * slow;
    }
    return {
      kind: "basic", smooth: smooth, effort: effort, ok: true,
      text: text, label: "빠르기 " + WORD[smooth] + ", 힘 " + WORD[effort],
      key: "s" + smooth + "e" + effort, fn: fn,
      debug: function (phi, w, v, u) {
        var values = [1 - 0.3 * phi * phi, -ws * w * w - 0.002 * v * v, -we * u * u, 0.5 * Math.exp(-11.111111 * phi * phi) * Math.exp(-0.25 * w * w)];
        var labels = ['직립 목표', '속도 감점', '지령 감점', '직립 보너스'], total = 0;
        return { value: fn(phi, w, v, u), issues: [], events: values.map(function (x, i) { total += x; return { id: null, kind: 'score', label: labels[i], value: x, total: total, vars: {} }; }) };
      }
    };
  }

  /* ── 블록 계산 ── */
  var MAX_STEPS = 2048;
  function context(v) {
    if (!v.ctx) v.ctx = { vars: { A: 0, B: 0, C: 0, D: 0 }, loops: [], signal: null, steps: 0 };
    return v.ctx;
  }
  function event(v, item) {
    var ctx = context(v);
    if (!ctx.events) return;
    item.total = ctx.total || 0; item.vars = Object.assign({}, ctx.vars);
    item.loop = ctx.loops.length ? ctx.loops[ctx.loops.length - 1] : null;
    ctx.events.push(item);
  }
  function spend(v, errors, id) {
    if (++context(v).steps <= MAX_STEPS) return true;
    fault(errors, id, 'execution-budget', '한 순간의 계산이 너무 많아요. 반복 횟수나 안쪽 블록 수를 줄여 주세요.');
    return false;
  }
  function fault(errors, id, code, message) {
    if (errors && !errors.some(function (e) { return e.id === id && e.code === code; })) errors.push({ level: 'error', code: code, id: id, message: message });
  }
  function finite(value, errors, id) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    fault(errors, id, 'calculation-overflow', '이 블록의 계산이 너무 커지거나 유효한 숫자가 아니에요. 값의 크기와 계산식을 확인해 주세요.');
    return 0;
  }
  function numOf(M, slot, v, depth, errors, owner) {
    if (!slot) return 0;
    return slot.block != null ? valOf(M, slot.block, v, depth, errors) : finite(slot.v, errors, owner);
  }
  function boolSlot(M, slot, v, depth, errors) {
    return slot && slot.block != null ? boolOf(M, slot.block, v, depth, errors) : false;
  }
  function valOf(M, id, v, depth, errors) {
    var value = rawValOf(M, id, v, depth, errors);
    event(v, { id: id, kind: 'value', value: value });
    return value;
  }
  function rawValOf(M, id, v, depth, errors) {
    var b = M.B[id];
    if (!b || (depth || 0) > 40) return 0;
    var d = PS.DEFS[b.type];
    if (!d) return 0;
    if (!spend(v, errors, id)) return 0;
    try {
      if (b.type === 'get_var') return finite(context(v).vars[b.f.variable], errors, id);
      if (b.type === 'loop_index') {
        var loops = context(v).loops;
        if (!loops.length) { fault(errors, id, 'outside-loop', '이번 반복 번호는 반복 안에서 사용하세요.'); return 0; }
        return loops[loops.length - 1];
      }
      if (b.type === 'choose') return numOf(M, b.s[boolSlot(M, b.s[0], v, (depth || 0) + 1, errors) ? 1 : 2], v, (depth || 0) + 1, errors, id);
      if (d.read) return finite(d.read(v), errors, id);
      var args = b.s.map(function (s) { return numOf(M, s, v, (depth || 0) + 1, errors, id); });
      if (b.type === 'div' && args[1] === 0) { fault(errors, id, 'divide-zero', '나누는 값이 0이 되었어요. 0이 아닌 경우만 계산하도록 조건을 넣거나 분모에 양수 하한을 사용해 주세요.'); return 0; }
      if (b.type === 'clamp' && args[1] > args[2]) { fault(errors, id, 'reversed-range', '범위를 제한하는 블록에서 최솟값이 최댓값보다 커졌어요. 경계값의 순서를 확인해 주세요.'); return 0; }
      args.push(b.f);
      return finite(d.fn ? d.fn.apply(null, args) : 0, errors, id);
    } catch (_) { fault(errors, id, 'calculation-error', '이 계산을 읽을 수 없어요. 입력 칸을 확인해 주세요.'); return 0; }
  }
  function boolOf(M, id, v, depth, errors) {
    var value = rawBoolOf(M, id, v, depth, errors);
    event(v, { id: id, kind: 'condition', value: value });
    return value;
  }
  function rawBoolOf(M, id, v, depth, errors) {
    var b = M.B[id];
    if (!b || (depth || 0) > 40) return false;
    var d = PS.DEFS[b.type];
    if (!d) return false;
    if (!spend(v, errors, id)) return false;
    try {
      if (d.test) return !!d.test(v);
      var args = b.s.map(function (s) { return d.fnb ? boolSlot(M, s, v, (depth || 0) + 1, errors) : numOf(M, s, v, (depth || 0) + 1, errors, id); });
      if (b.type === 'between' && args[1] > args[2]) { fault(errors, id, 'reversed-range', '범위를 판단하는 블록에서 최솟값이 최댓값보다 커졌어요. 경계값의 순서를 확인해 주세요.'); return false; }
      args.push(b.f);
      if (d.fnb || d.fn) return !!(d.fnb || d.fn).apply(null, args);
    } catch (_) { fault(errors, id, 'condition-error', '이 조건을 읽을 수 없어요. 판단 블록의 입력 칸을 확인해 주세요.'); }
    return false;
  }
  function runList(M, list, v, tr, depth, errors) {
    var sum = 0;
    var ctx = context(v);
    if ((depth || 0) > 40) return 0;
    for (var i = 0; i < list.length; i++) {
      var b = M.B[list[i]];
      if (!b) continue;
      if (ctx.signal || errors && errors.length || !spend(v, errors, b.id)) break;
      if (b.type === "plus" || b.type === "minus") {
        var x = numOf(M, b.s[0], v, 0, errors, b.id);
        if (b.type === "minus") x = -x;
        sum = finite(sum + x, errors, b.id);
        if (ctx.events) { ctx.total = (ctx.total || 0) + x; event(v, { id: b.id, kind: 'score', value: x }); }
        if (tr) tr[b.id] = (tr[b.id] || 0) + x;
      } else if (b.type === 'set_var' || b.type === 'change_var') {
        var key = b.f.variable, val = numOf(M, b.s[0], v, 0, errors, b.id);
        if (!Object.prototype.hasOwnProperty.call(ctx.vars, key)) { fault(errors, b.id, 'unknown-variable', '변수 목록에서 사용할 변수를 골라 주세요.'); break; }
        ctx.vars[key] = finite((b.type === 'change_var' ? ctx.vars[key] : 0) + val, errors, b.id);
        event(v, { id: b.id, kind: 'variable', value: ctx.vars[key], variable: key });
        if (tr) tr[b.id] = ctx.vars[key];
      } else if (b.type === 'break_loop' || b.type === 'continue_loop') {
        if (!ctx.loops.length) fault(errors, b.id, 'outside-loop', '반복 중단·건너뛰기는 반복 안에 놓아 주세요.');
        else ctx.signal = b.type;
        event(v, { id: b.id, kind: b.type, value: null });
      } else if (b.type === 'repeat') {
        var count = numOf(M, b.s[0], v, 0, errors, b.id);
        if (!Number.isInteger(count) || count < 0 || count > 20) { fault(errors, b.id, 'repeat-range', '반복 횟수는 0~20 사이 정수여야 해요.'); break; }
        ctx.loops.push(0);
        event(v, { id: b.id, kind: 'repeat', value: count });
        for (var k = 1; k <= count; k++) {
          if (errors && errors.length || !spend(v, errors, b.id)) break;
          ctx.loops[ctx.loops.length - 1] = k;
          event(v, { id: b.id, kind: 'iteration', value: k });
          sum = finite(sum + runList(M, b.bodies[0], v, tr, (depth || 0) + 1, errors), errors, b.id);
          var stop = ctx.signal === 'break_loop'; ctx.signal = null;
          if (stop) break;
        }
        ctx.loops.pop();
      } else if (b.type === "if" || b.type === "ifelse") {
        var c = boolSlot(M, b.s[0], v, 0, errors);
        if (c) sum = finite(sum + runList(M, b.bodies[0], v, tr, (depth || 0) + 1, errors), errors, b.id);
        else if (b.type === "ifelse") sum = finite(sum + runList(M, b.bodies[1], v, tr, (depth || 0) + 1, errors), errors, b.id);
      }
    }
    return sum;
  }

  /* ── 글로 옮기기 (기록 표와 도움말에 씀) ── */
  function num(x) { return Number.isFinite(x) ? String(Math.abs(x) < 1e12 ? Math.round(x * 1000) / 1000 : x) : '?'; }
  function slotText(M, slot, spec, depth) {
    if (!slot) return '?';
    if (slot.block) return blockText(M, slot.block, depth);
    return spec.s === "bool" ? "?" : Number.isFinite(slot.v) ? String(slot.v) : '?';
  }
  function blockText(M, id, depth) {
    var b = M.B[id];
    if (!b || !PS.DEFS[b.type] || (depth || 0) > 40) return "?";
    var d = PS.DEFS[b.type], out = [], k = 0;
    d.tpl.forEach(function (p) {
      if (typeof p === "string") out.push(p);
      else if (p.s) { out.push(slotText(M, b.s[k], p, (depth || 0) + 1)); k++; }
      else if (p.dd) {
        var lab = "";
        p.opts.forEach(function (o) { if (String(o[0]) === String(b.f[p.dd])) lab = o[1]; });
        if (p.dd === 'variable') lab = PS.variableName(M, b.f.variable);
        out.push(lab);
      }
    });
    var t = out.join(" ").replace(/ 값/g, "").replace(/\s+/g, " ").trim();
    return d.shape === "val" && b.s.length > 1 ? "(" + t + ")" : t;
  }
  function listText(M, list, depth) {
    if (!Array.isArray(list) || (depth || 0) > 40) return '?';
    return list.map(function (id) {
      var b = M.B[id];
      if (!b) return "";
      if (b.type === "plus") return "+ " + slotText(M, b.s[0], { s: "num" });
      if (b.type === "minus") return "− " + slotText(M, b.s[0], { s: "num" });
      if (b.type === "if") return "만일 " + slotText(M, b.s[0], { s: "bool" }) + " 이면 { " + listText(M, b.bodies[0], (depth || 0) + 1) + " }";
      if (b.type === "ifelse") {
        return "만일 " + slotText(M, b.s[0], { s: "bool" }) + " 이면 { " + listText(M, b.bodies[0], (depth || 0) + 1) +
          " } 아니면 { " + listText(M, b.bodies[1], (depth || 0) + 1) + " }";
      }
      if (b.type === 'repeat') return slotText(M, b.s[0], { s: 'num' }) + '번 반복 { ' + listText(M, b.bodies[0], (depth || 0) + 1) + ' }';
      return blockText(M, id);
    }).filter(Boolean).join("  ");
  }
  function countScore(M, list, depth) {
    var n = 0;
    if (!Array.isArray(list) || (depth || 0) > 40) return 0;
    list.forEach(function (id) {
      var b = M.B[id];
      if (!b) return;
      if (b.type === "plus" || b.type === "minus") n++;
      (b.bodies || []).forEach(function (body) { n += countScore(M, body, (depth || 0) + 1); });
    });
    return n;
  }

  function inspect(M) {
    if (PS.BlockChecks) return PS.BlockChecks.inspect(M);
    return { ok: false, issues: [{ level: 'error', code: 'missing-checker', id: null, message: '블록 점검 기능을 읽지 못했어요. 앱을 다시 열어 주세요.' }], summary: '블록 점검을 읽지 못했어요.' };
  }
  /* Labels, positions and block IDs are not part of the policy contract. Keep
     full numeric precision, unlike the rounded human-readable rule text. */
  function signature(M) {
    function node(id, depth) {
      var b = M.B[id];
      if (!b || depth > 40) return null;
      var fields = Object.keys(b.f || {}).sort().map(function (key) { return [key, b.f[key]]; });
      return [b.type, (b.s || []).map(function (s) { return s.block != null ? ['block', node(s.block, depth + 1)] : ['number', s.v]; }), fields,
        (b.bodies || []).map(function (body) { return body.map(function (child) { return node(child, depth + 1); }); })];
    }
    return 'blocks-v2:' + JSON.stringify((M.scripts.reward || []).map(function (id) { return node(id, 1); }));
  }
  function blocks(M) {
    var list = M.scripts.reward;
    var diagnosis = inspect(M), text = listText(M, list), n = countScore(M, list);
    var ruleObject;
    function fn(phi, ald, thd, u, th) {
      var evaluated = evaluate(phi, ald, thd, u, th);
      ruleObject.lastError = evaluated.issues[0] || null;
      return evaluated.value;
    }
    function evaluate(phi, ald, thd, u, th) {
      var errors = diagnosis.ok ? [] : diagnosis.issues.filter(function (issue) { return issue.level === 'error'; });
      var value = diagnosis.ok ? runList(M, list, { phi: phi, ald: ald, thd: thd, u: u, th: th || 0 }, null, 0, errors) : 0;
      return { value: errors.length ? 0 : value, issues: errors };
    }
    function trace(phi, ald, thd, u, th) {
      var tr = {}, v = { phi: phi, ald: ald, thd: thd, u: u, th: th || 0 }, errors = [];
      if (!diagnosis.ok) return tr;
      runList(M, list, v, tr, 0, errors);
      if (errors.length) return {};
      tr.variables = context(v).vars;
      return tr;
    }
    function debug(phi, ald, thd, u, th) {
      var v = { phi: phi, ald: ald, thd: thd, u: u, th: th || 0 }, errors = diagnosis.issues.filter(function (i) { return i.level === 'error'; });
      context(v).events = []; context(v).total = 0;
      var value = diagnosis.ok ? runList(M, list, v, null, 0, errors) : 0;
      return { value: errors.length ? 0 : value, issues: errors, events: context(v).events.map(function (e) { e.label = blockText(M, e.id); return e; }) };
    }
    ruleObject = {
      kind: "blocks", ok: n > 0 && diagnosis.ok, issues: diagnosis.issues,
      text: text ? "점수 = " + text : "아직 점수 블록이 없습니다",
      label: text || "빈 규칙", key: signature(M), fn: fn, trace: trace, evaluate: evaluate, debug: debug, lastError: null
    };
    return ruleObject;
  }

  /* ── 시작하기 아래 블록 읽기 ── */
  function runOpts(M) {
    var diagnosis = inspect(M);
    var o = { gens: 24, pop: 20, sigma: 0.06, learn: false, test: null, ok: diagnosis.ok, issues: diagnosis.issues };
    (M.scripts.run || []).forEach(function (id) {
      var b = M.B[id];
      if (!b) return;
      var x = b.s.length ? numOf(M, b.s[0], { phi: 0, ald: 0, thd: 0, u: 0, th: 0 }, 0) : 0;
      if (b.type === "cond") {
        if (b.f.key === "gens") o.gens = Math.max(4, Math.min(80, Math.round(x)));
        if (b.f.key === "pop") o.pop = Math.max(6, Math.min(40, Math.round(x)));
        if (b.f.key === "sigma") o.sigma = Math.max(1, Math.min(30, x)) / 100;
      }
      if (b.type === "learn") o.learn = true;
      if (b.type === "test" && o.test === null) o.test = Math.max(3, Math.min(20, Math.round(x)));
    });
    return o;
  }

  /* ── 규칙 점검: 학습하기 전에 흔한 실수를 잡습니다 ── */
  function check(rule) {
    var issues = (rule.issues || []).slice();
    function finish(message) {
      var error = issues.find(function (i) { return i.level === 'error'; });
      var warn = issues.find(function (i) { return i.level === 'warn'; });
      return { level: error ? 'error' : warn ? 'warn' : 'ok', msg: error ? error.message : warn ? warn.message : message, issues: issues };
    }
    if (!rule.ok) {
      if (!issues.some(function (i) { return i.level === 'error'; })) issues.push({ level: 'error', code: 'empty-reward', id: null, message: '점수 더하기 또는 빼기를 매 순간 점수 매기기 아래에 연결해 주세요.' });
      return finish('');
    }
    function probe(phi, ald, thd, u, th) {
      var evaluated = rule.evaluate ? rule.evaluate(phi, ald, thd, u, th) : { value: rule.fn(phi, ald, thd, u, th), issues: [] };
      evaluated.issues.forEach(function (issue) { if (!issues.some(function (old) { return old.code === issue.code && old.id === issue.id; })) issues.push(issue); });
      if (!Number.isFinite(evaluated.value)) fault(issues, null, 'reward-overflow', '전체 점수가 너무 커져 계산할 수 없어요. 숫자와 계산의 크기를 줄여 주세요.');
      return Number.isFinite(evaluated.value) ? evaluated.value : 0;
    }
    var up = probe(0, 0, 0, 0, 0), hang = probe(Math.PI, 0, 0, 0, 0), spin = 0, n = 12;
    for (var i = 0; i < n; i++) spin += probe(PS.wrap(i / n * 2 * Math.PI), 20, 5, 1, 0) / n;
    // Illustrative states only, not a plant rollout or a control guarantee.
    probe(-Math.PI / 4, -2, -5, -0.5, -Math.PI);
    probe(Math.PI / 4, 2, 5, 0.5, Math.PI);
    if (up <= hang) {
      issues.push({ level: 'warn', code: 'hanging-reward', id: null, message: "매달려 있을 때 점수(" + num(hang) + ")가 똑바로 섰을 때(" + num(up) +
        ")보다 높거나 같아요. 더하기와 빼기를 확인해 보세요." });
    }
    if (spin > up) {
      issues.push({ level: 'warn', code: 'spinning-reward', id: null, message: '확인한 회전 예시의 평균 점수가 직립보다 높아요. 빠르게 돌리는 행동을 원한 것인지 살펴보세요.' });
    }
    return finish('확인한 예시에서 직립 점수(' + num(up) + ')가 매달림 점수(' + num(hang) + ')보다 높아요. 실제 학습 결과는 실험으로 비교하세요.');
  }

  PS.reward = {
    basic: basic, blocks: blocks, runOpts: runOpts, check: check, WORD: WORD,
    blockText: blockText, valOf: valOf, boolOf: boolOf, inspect: inspect, signature: signature, MAX_STEPS: MAX_STEPS
  };
})(window.PS = window.PS || {});
