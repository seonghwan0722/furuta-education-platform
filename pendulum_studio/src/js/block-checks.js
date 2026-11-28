/* Read-only classroom diagnostics. No controller, training or device calls. */
(function (PS) {
  'use strict';
  var OWN = Object.prototype.hasOwnProperty;
  var LIMIT = 40;
  function inspect(M) {
    var issues = [], seen = {}, activePath = {}, scoreCount = 0, issueKeys = {};
    var B = M && M.B || {}, defs = PS.DEFS || {};
    function add(level, code, id, message, slot, live) {
      if (live === false && level === 'error') level = 'warn';
      var key = level + ':' + code + ':' + id + ':' + slot;
      if (issueKeys[key]) return;
      issueKeys[key] = true;
      var item = { level: level, code: code, id: id == null ? null : +id, message: message };
      if (slot != null) item.slot = slot;
      issues.push(item);
    }
    function unknown() { return { constant: false, state: false, unit: '' }; }
    function mismatch(a, b, id, slot, live) {
      if (a && b && a !== b && a !== 'number' && b !== 'number')
        add('warn', 'unit-mismatch', id, '서로 다른 단위(' + a + ', ' + b + ')를 함께 계산하거나 비교하고 있어요. 같은 기준으로 바꾼 값인지 확인하세요.', slot, live);
    }
    function visit(id, expected, domain, depth, live) {
      if (depth > LIMIT) { add('error', 'too-deep', id, '블록은 40단계까지만 중첩할 수 있어요. 계산이나 조건을 단순하게 나눠 주세요.', null, live); return unknown(); }
      var b = B[id], d = b && OWN.call(defs, b.type) && defs[b.type];
      if (!d) { add('error', 'missing-block', id, '연결된 블록을 읽을 수 없어요. 이 연결을 다시 만들어 주세요.', null, live); return unknown(); }
      if (activePath[id]) { add('error', 'cycle', id, '블록이 자기 자신에게 다시 연결되어 있어요. 연결을 풀어 주세요.', null, live); return unknown(); }
      if (live && seen[id]) { add('error', 'duplicate-link', id, '같은 블록이 두 곳에 연결되어 있어요. 한쪽 연결을 풀어 주세요.', null, live); return unknown(); }
      if (live) seen[id] = true;
      activePath[id] = true;
      if (expected === 'stack' ? !(['stk', 'c'].indexOf(d.shape) >= 0 && d.dom === domain) : d.shape !== expected)
        add('error', 'wrong-place', id, '이 블록은 현재 칸에 들어갈 수 없어요. 숫자는 둥근 칸, 판단은 육각 칸, 점수와 실행 블록은 각각의 시작 블록 아래에 놓으세요.', null, live);
      var specs = d.tpl.filter(function (p) { return p && typeof p === 'object' && p.s; });
      var fields = d.tpl.filter(function (p) { return p && typeof p === 'object' && p.dd; });
      var slots = Array.isArray(b.s) ? b.s : [], bodies = Array.isArray(b.bodies) ? b.bodies : [];
      if (slots.length !== specs.length || bodies.length !== (d.bodies || 0)) add('error', 'bad-structure', id, '블록의 입력 칸이나 안쪽 구조가 맞지 않아요. 이 블록을 다시 넣어 주세요.', null, live);
      fields.forEach(function (p) {
        if (!b.f || !p.opts.some(function (o) { return o[0] === b.f[p.dd]; })) add('error', 'bad-option', id, '고르는 칸의 값이 올바르지 않아요. 목록에서 다시 골라 주세요.', null, live);
      });
      var args = specs.map(function (spec, index) {
        var s = slots[index];
        if (!s) { add('error', 'missing-slot', id, '입력 칸을 읽을 수 없어요. 블록을 다시 넣어 주세요.', index, live); return unknown(); }
        if (s.block != null) return visit(s.block, spec.s === 'bool' ? 'bool' : 'val', domain, depth + 1, live);
        if (spec.s === 'bool') { add('error', 'empty-condition', id, '비어 있는 육각 칸에 판단 블록을 넣어 주세요. 빈칸은 거짓이라는 뜻이 아니에요.', index, live); return unknown(); }
        if (typeof s.v !== 'number' || !Number.isFinite(s.v)) { add('error', 'invalid-number', id, '숫자 칸에는 유한한 숫자를 넣어 주세요. 빈칸·문자·무한대는 사용할 수 없어요.', index, live); return unknown(); }
        return { constant: true, value: s.v, state: false, unit: 'number' };
      });
      var children = [];
      bodies.forEach(function (body, index) {
        if (!Array.isArray(body)) { add('error', 'bad-body', id, '조건 안쪽 블록 묶음을 읽을 수 없어요.', null, live); return; }
        if (!body.length) add('warn', 'empty-branch-' + index, id, (index ? '아니면' : '참일 때') + ' 안쪽이 비어 있어요. 이 경우에는 점수가 더해지거나 빠지지 않아요.', null, live);
        body.forEach(function (child) { children.push(visit(child, 'stack', domain, depth + 1, live)); });
      });
      delete activePath[id];
      var state = !!(d.read || d.test) || args.concat(children).some(function (a) { return a.state; });
      if (b.type === 'true' || b.type === 'false' || OWN.call(d, 'literal')) state = false;
      var result = { constant: false, state: state, unit: d.unit || '' };
      if (b.type === 'plus' || b.type === 'minus') {
        if (live && domain === 'reward') scoreCount++;
        if (b.type === 'minus' && args[0] && args[0].constant && args[0].value < 0)
          add('warn', 'negative-penalty', id, '음수를 빼면 오히려 점수가 올라가요. 감점하려면 양수를 빼세요.', 0, live);
      }
      if ((b.type === 'if' || b.type === 'ifelse') && args[0] && args[0].constant)
        add('warn', 'constant-condition', id, '이 조건은 항상 ' + (args[0].value ? '참' : '거짓') + '이에요. 진자의 상태에 따라 달라지는 조건이 필요한지 확인하세요.', 0, live);
      if (b.type === 'div' && args[1]) {
        if (args[1].constant && args[1].value === 0) add('error', 'divide-zero', id, '0으로 나눌 수 없어요. 오른쪽 숫자나 계산을 바꿔 주세요.', 1, live);
        else if (!args[1].constant) add('warn', 'variable-denominator', id, '오른쪽 값이 0이 되면 계산을 중단해요. 0이 아닌 경우에만 계산하는 조건이나 양수 하한을 써 보세요.', 1, live);
      }
      if ((b.type === 'between' || b.type === 'clamp') && args[1] && args[2] && args[1].constant && args[2].constant && args[1].value > args[2].value)
        add('error', 'reversed-range', id, '최솟값이 최댓값보다 커요. 두 경계값의 순서를 바꿔 주세요.', 1, live);
      if ((b.type === 'between' || b.type === 'clamp') && args[1] && args[2] && (!args[1].constant || !args[2].constant))
        add('warn', 'variable-range', id, '범위의 경계값이 상태에 따라 바뀌어요. 최솟값이 최댓값보다 커지는 순간에는 계산을 중단하므로, 항상 순서가 맞도록 정해 주세요.', 1, live);
      if (['add', 'sub', 'lt', 'le', 'gt', 'ge', 'eq', 'neq', 'min', 'max'].indexOf(b.type) >= 0 && args[0] && args[1]) mismatch(args[0].unit, args[1].unit, id, 1, live);
      if ((b.type === 'between' || b.type === 'clamp') && args[0]) {
        if (args[1]) mismatch(args[0].unit, args[1].unit, id, 1, live);
        if (args[2]) mismatch(args[0].unit, args[2].unit, id, 2, live);
      }
      if ((!result.unit || result.unit === 'number') && args.length) {
        if (['add', 'sub', 'min', 'max', 'clamp'].indexOf(b.type) >= 0) result.unit = args[0].unit === 'number' && args[1] ? args[1].unit : args[0].unit;
        else if (b.type === 'mul') result.unit = args[0].unit === 'number' ? args[1].unit : args[1].unit === 'number' ? args[0].unit : args[0].unit + '·' + args[1].unit;
        else if (b.type === 'div') result.unit = args[1].unit === 'number' ? args[0].unit : args[0].unit === args[1].unit ? 'number' : args[0].unit + '/' + args[1].unit;
        else if (b.type === 'pow') result.unit = args[0].unit + (b.f && b.f.op === 'abs' ? '' : '²');
      }
      if (b.type === 'true' || b.type === 'false' || OWN.call(d, 'literal')) { result.constant = true; result.value = OWN.call(d, 'literal') ? d.literal : b.type === 'true'; }
      else if (!d.read && !d.test && args.every(function (a) { return a.constant; }) && (d.fn || d.fnb)) {
        try {
          var values = args.map(function (a) { return a.value; }); values.push(b.f || {});
          var value = (d.fn || d.fnb).apply(null, values);
          if (d.shape === 'bool') { result.constant = true; result.value = !!value; }
          else if (typeof value === 'number' && Number.isFinite(value)) { result.constant = true; result.value = value; }
          else add('error', 'constant-overflow', id, '이 계산의 결과가 너무 크거나 숫자가 아니에요. 입력값이나 계산을 작게 나눠 주세요.', null, live);
        } catch (_) { add('error', 'constant-calculation', id, '이 계산을 읽을 수 없어요. 입력 칸을 확인해 주세요.', null, live); }
      }
      if (live && domain === 'run' && (b.type === 'cond' || b.type === 'test') && args[0]) {
        if (!args[0].constant) add('error', 'dynamic-run-option', id, '학습 조건과 시험 시간은 시작 전에 정하는 고정 숫자예요. 키트 상태 대신 숫자나 숫자끼리의 계산을 넣어 주세요.', 0, live);
        else {
          var key = b.type === 'test' ? 'seconds' : b.f && b.f.key;
          var ranges = { gens: {min:4,max:80,integer:true}, pop: {min:6,max:40,integer:true}, sigma: {min:1,max:30,integer:false}, seconds: {min:3,max:20,integer:true} };
          var spec = PS.numericSpec ? PS.numericSpec(b.type, b.f, 0) : ranges[key], x = args[0].value;
          if (spec && (x < spec.min || x > spec.max || spec.integer && !Number.isInteger(x)))
            add('error', 'run-option-range', id, '이 값은 ' + spec.min + '~' + spec.max + (spec.integer ? ' 사이의 정수' : ' 사이의 숫자') + '로 입력해 주세요. 적힌 값과 실행값이 같아야 해요.', 0, live);
        }
      }
      return result;
    }
    if (!M || !M.B || !M.scripts) add('error', 'missing-model', null, '블록 작업 내용을 읽을 수 없어요. 프로젝트를 다시 확인해 주세요.');
    if (Object.keys(B).length > 1000) add('error', 'too-many-blocks', null, '블록은 1,000개까지 사용할 수 있어요. 사용하지 않는 블록을 정리해 주세요.');
    var reward = M && M.scripts && M.scripts.reward, run = M && M.scripts && M.scripts.run;
    var rewardNodes = Array.isArray(reward) ? reward.map(function (id) { return visit(id, 'stack', 'reward', 1, true); }) : [];
    if (!scoreCount) add('error', 'empty-reward', null, '매 순간 점수 매기기 아래에 점수 더하기 또는 빼기를 연결해 주세요.');
    else if (!rewardNodes.some(function (a) { return a.state; })) add('warn', 'constant-reward', reward[0], '점수가 진자의 상태나 행동에 따라 달라지지 않아요. 무엇을 잘했을 때 점수를 줄지 키트 값이나 조건을 연결해 보세요.');
    if (!Array.isArray(run) || !run.length) add('error', 'empty-run', null, '시작하기 아래에 학습하기 또는 시험하기 블록을 연결해 주세요.');
    var phase = 0, learns = 0, tests = 0, conds = {};
    (Array.isArray(run) ? run : []).forEach(function (id) {
      visit(id, 'stack', 'run', 1, true);
      var b = B[id]; if (!b) return;
      if (b.type === 'cond') {
        if (phase) add('error', 'late-condition', id, '학습 조건은 학습하기·시험하기보다 위에 놓아 주세요.');
        var key = b.f && b.f.key;
        if (conds[key]) add('warn', 'duplicate-option', id, '같은 학습 조건이 여러 번 있어요. 가장 아래의 값이 적용됩니다. 하나로 정리하면 읽기 쉬워요.');
        conds[key] = true;
      } else if (b.type === 'learn') {
        if (++learns > 1) add('error', 'duplicate-learn', id, '한 번의 시작에서는 학습하기를 하나만 사용할 수 있어요.');
        if (phase === 2) add('error', 'learn-after-test', id, '학습하기를 시험하기 위로 옮겨 주세요. 시험 후 다시 학습하는 순서는 지원하지 않아요.');
        phase = Math.max(phase, 1);
      } else if (b.type === 'test') {
        if (++tests > 1) add('error', 'duplicate-test', id, '한 번의 시작에서는 시험하기를 하나만 사용할 수 있어요. 다시 시험하려면 시작하기를 다시 누르세요.');
        phase = 2;
      }
    });
    if (Array.isArray(run) && run.length && !learns && !tests) add('error', 'no-run-action', run[0], '조건만으로는 학습이나 시험을 시작하지 않아요. 학습하기 또는 시험하기를 연결해 주세요.');
    (M && Array.isArray(M.loose) ? M.loose : []).forEach(function (group) {
      (Array.isArray(group.ids) ? group.ids : []).forEach(function (id) {
        if (!seen[id]) add('warn', 'unused-block', id, '따로 놓인 블록은 실행되지 않아요. 사용할 블록은 점수 규칙이나 시작하기 아래에 연결해 주세요.');
      });
    });
    var errors = issues.filter(function (i) { return i.level === 'error'; }).length;
    var warnings = issues.length - errors;
    return { ok: errors === 0, issues: issues, summary: errors ? '고칠 곳 ' + errors + '개' : warnings ? '확인할 점 ' + warnings + '개' : '블록 연결과 입력을 확인했어요.' };
  }
  PS.BlockChecks = { inspect: inspect, MAX_DEPTH: LIMIT };
})(window.PS = window.PS || {});
