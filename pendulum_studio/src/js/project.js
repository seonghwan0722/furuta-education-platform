/* Classroom project files: declarative data only. Validation never changes the running app.
 * v4 (.pendulum): rules, policy, immutable experiments, missions and all lesson views.
 * v3 files are migrated with no invented classroom history.
 * v2 (.json): the earlier rule-only format, migrated without a policy or device state.
 */
(function (PS) {
  "use strict";

  var MAX_BYTES = 8 * 1024 * 1024;
  var OWN = Object.prototype.hasOwnProperty;

  function fail(message) { throw new Error(message); }
  function object(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value)) fail(label + " 형식이 올바르지 않습니다.");
    return value;
  }
  function array(value, max, label) {
    if (!Array.isArray(value) || value.length > max) fail(label + " 목록이 없거나 너무 큽니다.");
    return value;
  }
  function text(value, max, label) {
    if (typeof value !== "string" || value.length > max) fail(label + " 글자 수 또는 형식이 올바르지 않습니다.");
    return value;
  }
  function number(value, min, max, label) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) fail(label + " 숫자가 올바르지 않습니다.");
    return value;
  }
  function integer(value, min, max, label) {
    number(value, min, max, label);
    if (!Number.isInteger(value)) fail(label + " 값은 정수여야 합니다.");
    return value;
  }
  function bool(value, label) {
    if (typeof value !== "boolean") fail(label + " 값이 올바르지 않습니다.");
    return value;
  }
  function choice(value, options, label) {
    if (options.indexOf(value) === -1) fail(label + " 값이 지원되지 않습니다.");
    return value;
  }
  function optionalNumber(value, label) {
    return value === null ? null : number(value, 0, Number.MAX_VALUE, label);
  }
  function byteLength(value) { return new TextEncoder().encode(value).length; }
  function limitedText(value) {
    if (typeof value !== "string" || value.length > MAX_BYTES || byteLength(value) > MAX_BYTES) fail("프로젝트 파일은 8 MB 이하여야 합니다.");
    return value;
  }
  function id(value) { return integer(value, 1, 1000000000, "블록 번호"); }
  function point(value) {
    if (value === null) return null;
    object(value, "블록 위치");
    return { x: number(value.x, 0, 1000000, "블록 가로 위치"), y: number(value.y, 0, 1000000, "블록 세로 위치") };
  }

  function blockModel(value, legacy) {
    object(value, "블록");
    var source = object(value.B, "블록 목록"), keys = Object.keys(source);
    if (keys.length > 1000) fail("블록은 1,000개까지 저장할 수 있습니다.");
    var model = { B: {}, scripts: { reward: [], run: [] }, pos: { reward: null, run: null }, loose: [], next: 1 };
    if (value.variables !== undefined) {
      object(value.variables, '변수 이름'); model.variables = {};
      var names = [];
      ['A', 'B', 'C', 'D'].forEach(function (key) {
        var name = value.variables[key] === undefined ? '변수 ' + key : text(value.variables[key], 16, '변수 이름').trim();
        if (!name || /[\x00-\x1f\x7f]/.test(name) || names.indexOf(name) >= 0) fail('변수 이름은 서로 다른 1~16자 이름으로 정해 주세요.');
        model.variables[key] = name; names.push(name);
      });
    }
    var defs = PS.DEFS, parents = {}, edges = {}, largest = 0;
    if (!defs) fail("블록 정의를 읽지 못했습니다. 앱을 다시 열어 주세요.");

    keys.forEach(function (key) {
      if (!/^[1-9][0-9]*$/.test(key) || String(id(+key)) !== key) fail("블록 번호가 올바르지 않습니다.");
      var b = object(source[key], "블록"), type = text(b.type, 80, "블록 종류");
      if (!OWN.call(defs, type)) fail("현재 앱에서 지원하지 않는 블록이 있습니다.");
      if (id(b.id) !== +key) fail("블록 번호와 목록의 번호가 다릅니다.");
      var d = defs[type], slots = d.tpl.filter(function (p) { return p && typeof p === "object" && p.s; });
      var fields = d.tpl.filter(function (p) { return p && typeof p === "object" && p.dd; });
      var inputSlots = array(b.s, 20, "블록 입력 칸"), inputBodies = array(b.bodies, 4, "블록 안쪽");
      if (inputSlots.length !== slots.length || inputBodies.length !== (d.bodies || 0)) fail("블록의 입력 칸 또는 안쪽 구조가 다릅니다.");
      var inputFields = object(b.f, "블록 선택 값");
      var out = { id: b.id, type: type, s: [], f: {}, bodies: [] };
      inputSlots.forEach(function (s) {
        object(s, "블록 입력 칸");
        out.s.push({ block: s.block === null ? null : id(s.block), v: number(s.v, -Number.MAX_VALUE, Number.MAX_VALUE, "블록 입력") });
      });
      fields.forEach(function (f) {
        var val = inputFields[f.dd];
        var option = f.opts.find(function (o) { return o[0] === val; });
        if (!option) fail("블록의 고르는 칸에 지원하지 않는 값이 있습니다.");
        out.f[f.dd] = option[0];
      });
      out.bodies = inputBodies.map(function (list) { return array(list, 1000, "안쪽 블록").map(id); });
      model.B[key] = out;
      parents[key] = 0;
      edges[key] = [];
      largest = Math.max(largest, b.id);
    });

    function ref(blockId, owner) {
      if (!OWN.call(model.B, blockId)) fail("연결된 블록을 찾을 수 없습니다.");
      if (++parents[blockId] > 1) fail("하나의 블록이 여러 곳에 중복 연결되어 있습니다.");
      if (owner !== null) edges[owner].push(blockId);
      return model.B[blockId];
    }
    function stack(list, domain, owner) {
      return array(list, 1000, "블록 묶음").map(function (blockId) {
        id(blockId);
        var b = ref(blockId, owner), d = defs[b.type];
        if ((d.shape !== "stk" && d.shape !== "c") || d.dom !== domain) fail("블록이 들어갈 수 없는 위치에 연결되어 있습니다.");
        return blockId;
      });
    }

    keys.forEach(function (key) {
      var b = model.B[key], d = defs[b.type];
      var slots = d.tpl.filter(function (p) { return p && typeof p === "object" && p.s; });
      b.s.forEach(function (s, i) {
        if (s.block === null) return;
        var child = ref(s.block, key);
        if (defs[child.type].shape !== (slots[i].s === "num" ? "val" : "bool")) fail("숫자 칸과 판단 칸의 블록 종류가 맞지 않습니다.");
      });
      b.bodies = b.bodies.map(function (list) { return stack(list, d.dom, key); });
    });
    var scripts = object(value.scripts, "시작 블록 묶음");
    model.scripts.reward = stack(scripts.reward, "reward", null);
    model.scripts.run = stack(scripts.run, "run", null);
    var positions = value.pos;
    if (legacy && positions === undefined) positions = { reward: null, run: null };
    object(positions, "블록 묶음 위치");
    model.pos = { reward: point(positions.reward), run: point(positions.run) };
    var looseIds = {};
    var loose = legacy && value.loose === undefined ? [] : value.loose;
    model.loose = array(loose, 1000, "따로 놓은 블록").map(function (item) {
      object(item, "따로 놓은 블록");
      var lid = id(item.lid);
      if (looseIds[lid] || OWN.call(model.B, lid)) fail("따로 놓은 블록 묶음의 번호가 중복되었습니다.");
      looseIds[lid] = true;
      largest = Math.max(largest, lid);
      var ids = array(item.ids, 1000, "따로 놓은 블록 번호").map(id);
      if (!ids.length || !OWN.call(model.B, ids[0])) fail("따로 놓은 블록 묶음이 비어 있거나 연결이 없습니다.");
      var first = defs[model.B[ids[0]].type];
      if (first.shape === "val" || first.shape === "bool") {
        if (ids.length !== 1) fail("값 블록은 하나씩 따로 놓아야 합니다.");
        ref(ids[0], null);
      } else ids = stack(ids, first.dom, null);
      var xy = point({ x: item.x, y: item.y });
      return { lid: lid, x: xy.x, y: xy.y, ids: ids };
    });

    // Check every component, including currently unattached nodes retained by older editors.
    var visiting = {}, depths = {};
    function depth(key) {
      if (visiting[key]) fail("블록 연결이 순환하고 있습니다.");
      if (depths[key]) return depths[key];
      visiting[key] = true;
      var n = 1;
      edges[key].forEach(function (child) { n = Math.max(n, 1 + depth(child)); });
      visiting[key] = false;
      if (n > 40) fail("블록 중첩은 40단계 이하여야 합니다.");
      depths[key] = n;
      return n;
    }
    keys.forEach(depth);
    model.next = integer(value.next, 1, 1000000000, "다음 블록 번호");
    if (model.next <= largest) fail("다음 블록 번호가 기존 블록과 겹칩니다.");
    return model;
  }

  function runtime(C, obsN) {
    return { modelName: C.name, modelSignature: JSON.stringify(C), observationSize: obsN, contract: "pendulum-mlp-v1" };
  }
  function runtimeData(value) {
    if (value === null) return null;
    object(value, "환경 정보");
    return {
      modelName: text(value.modelName, 200, "환경 이름"),
      modelSignature: text(value.modelSignature, 65536, "환경 정보"),
      observationSize: integer(value.observationSize, 1, 128, "관측값 개수"),
      contract: text(value.contract, 80, "정책 규약")
    };
  }
  function sameRuntime(a, b) {
    return !!a && !!b && a.modelName === b.modelName && a.modelSignature === b.modelSignature &&
      a.observationSize === b.observationSize && a.contract === b.contract;
  }
  function capturePolicy(mlp) {
    if (!mlp) return null;
    return {
      name: mlp.name || "", algo: mlp.algo || "", activation: mlp.act === Math.tanh ? "tanh" : "relu", squash: mlp.squash,
      layers: mlp.layers.map(function (l) {
        var w = [];
        for (var i = 0; i < l.rows; i++) w.push(Array.from(l.w.slice(i * l.cols, (i + 1) * l.cols)));
        return { w: w, b: Array.from(l.b) };
      })
    };
  }
  function policy(value, observationSize) {
    object(value, "정책");
    var layers = array(value.layers, 6, "신경망 층");
    if (!layers.length) fail("정책 신경망에 층이 없습니다.");
    var expected = observationSize, count = 0;
    var result = {
      name: text(value.name, 200, "정책 이름"), algo: text(value.algo, 80, "알고리즘 이름"),
      activation: choice(value.activation, ["tanh", "relu"], "활성화 함수"), squash: bool(value.squash, "정책 출력 방식"), layers: []
    };
    result.layers = layers.map(function (layer) {
      object(layer, "신경망 층");
      var w = array(layer.w, 128, "신경망 가중치"), b = array(layer.b, 128, "신경망 편향");
      if (!w.length || b.length !== w.length) fail("신경망 가중치와 편향의 크기가 맞지 않습니다.");
      var out = { w: [], b: [] };
      out.w = w.map(function (row) {
        array(row, 128, "신경망 가중치 행");
        if (row.length !== expected) fail("정책 입력 또는 신경망 층의 연결 크기가 맞지 않습니다.");
        count += row.length;
        return row.map(function (x) { return number(x, -Number.MAX_VALUE, Number.MAX_VALUE, "정책 가중치"); });
      });
      out.b = b.map(function (x) { return number(x, -Number.MAX_VALUE, Number.MAX_VALUE, "정책 편향"); });
      count += b.length;
      if (count > 65000) fail("정책 신경망이 너무 큽니다.");
      expected = w.length;
      return out;
    });
    if (expected !== 1) fail("정책 출력은 모터 힘 하나여야 합니다.");
    return result;
  }

  function series(value, label, positive) {
    return array(value, 10000, label).map(function (x) {
      return number(x, positive ? 0 : -Number.MAX_VALUE, Number.MAX_VALUE, label);
    });
  }
  function runData(value) {
    object(value, "그래프 기록");
    var result = {
      label: text(value.label, 50000, "그래프 제목"), curve: series(value.curve, "학습 점수", false),
      t: series(value.t, "시간", true), height: series(value.height, "진자 높이", true),
      force: series(value.force, "모터 힘", true), arm: series(value.arm, "팔 회전", true),
      secs: number(value.secs, 3, 20, "실험 시간")
    };
    if (result.height.length !== result.t.length || result.force.length !== result.t.length || result.arm.length !== result.t.length) fail("그래프의 시간과 측정값 개수가 다릅니다.");
    ['error', 'velocity', 'action'].forEach(function (key) {
      if (value[key] !== undefined) { result[key] = series(value[key], key, false); if (result[key].length !== result.t.length) fail('상세 실험 기록의 길이가 다릅니다.'); }
    });
    result.t.forEach(function (t, i) {
      if (i && t < result.t[i - 1]) fail("그래프의 시간 순서가 올바르지 않습니다.");
    });
    return result;
  }
  function blankRun() { return { label: "", curve: [], t: [], height: [], force: [], arm: [], secs: 10 }; }
  function metrics(value) {
    if (value === null) return null;
    object(value, "실험 요약");
    return { up: optionalNumber(value.up, "직립 시간"), force: optionalNumber(value.force, "평균 힘"), arm: optionalNumber(value.arm, "팔 회전량") };
  }
  function results(value) {
    object(value, "실험 기록");
    var runNo = integer(value.runNo, 0, 1000000000, "실험 횟수"), numbers = {};
    var rows = array(value.rows, 100, "실험 기록").map(function (row) {
      object(row, "실험 기록 행");
      var no = integer(row.no, 1, runNo, "실험 번호");
      if (numbers[no]) fail("실험 번호가 중복되었습니다.");
      numbers[no] = true;
      return {
        no: no, label: text(row.label, 50000, "규칙 이름"), text: text(row.text, 50000, "규칙 설명"),
        sim: text(row.sim, 500, "시뮬레이션 기록"), kit: text(row.kit, 500, "키트 기록"),
        m: metrics(row.m), data: row.data === null ? null : runData(row.data),
        snapshot: row.snapshot ? experimentSnapshot(row.snapshot) : null,
        analysis: row.analysis ? analysis(row.analysis) : null
      };
    });
    function selected(no) {
      if (no === null) return null;
      integer(no, 1, runNo, "선택한 실험 번호");
      if (!numbers[no]) fail("선택한 실험 기록을 찾을 수 없습니다.");
      return no;
    }
    return { runNo: runNo, rows: rows, currentNo: selected(value.currentNo), pinnedNo: selected(value.pinnedNo), runData: runData(value.runData) };
  }

  function experimentSnapshot(value) {
    var s=PS.Classroom.data(value);
    text(s.rewardKey,50000,'보상 규칙');text(s.modelSignature,65536,'모델');text(s.source,20,'실행 위치');text(s.learningSource,200,'정책 준비 방식');text(s.policyDigest,100,'정책 식별');text(s.createdAt,40,'실험 시각');number(s.seconds,3,20,'시험 시간');object(s.options,'실험 조건');object(s.start,'시작 조건');
    if(s.blocks)s.blocks=blockModel(s.blocks,false);return s;
  }
  function analysis(value) {
    object(value,'상세 실험 지표');var out={};['duration','uprightSeconds','captureTime','postCaptureMAE','rmsAction'].forEach(function(k){out[k]=optionalNumber(value[k],k);});return out;
  }
  function normalize(value) {
    object(value, "프로젝트");
    if (value.app !== "pendulum-studio") fail("Pendulum Studio에서 저장한 수업 프로젝트가 아닙니다.");
    if ([2,3,4].indexOf(value.v) < 0) fail("지원하지 않는 프로젝트 버전입니다. 최신 앱인지 확인해 주세요.");
    var legacy = value.v === 2;
    var out = {
      app: "pendulum-studio", v: 4, name: text(value.name, 200, "작품 이름"),
      savedAt: legacy ? new Date().toISOString() : text(value.savedAt, 40, "저장 시각"),
      mode: choice(value.mode, ["guide", "free"], "수업 방식"),
      smooth: integer(legacy && value.smooth === undefined ? 1 : value.smooth, 0, 2, "빠르기 감점"),
      effort: integer(legacy && value.effort === undefined ? 1 : value.effort, 0, 2, "힘 감점"),
      blocks: blockModel(value.blocks, legacy), view: { step: 2, tab: "blocks" },
      progress: { done1: false, wrote: false }, runtime: null, learning: null,
      results: { runNo: 0, rows: [], currentNo: null, pinnedNo: null, runData: blankRun() },
      classroom: PS.Classroom.normalize(value.v === 4 ? value.classroom : null)
    };
    if (legacy) return { project: out, legacy: true };
    if (!/^\d{4}-\d{2}-\d{2}T/.test(out.savedAt) || !Number.isFinite(Date.parse(out.savedAt))) fail("저장 시각이 올바르지 않습니다.");
    var view = object(value.view, "화면 위치"), progress = object(value.progress, "수업 진행");
    out.view = { step: integer(view.step, 0, 3, "활동 번호"), tab: choice(view.tab, ["intro", "blocks", "graphs", "examples", "inquiry"], "화면 탭") };
    out.progress = { done1: bool(progress.done1, "살펴보기 진행"), wrote: bool(progress.wrote, "예상 작성 여부") };
    out.runtime = runtimeData(value.runtime);
    if (value.learning !== null) {
      var learning = object(value.learning, "학습 결과");
      if (!out.runtime) fail("정책을 확인할 환경 정보가 없습니다.");
      out.learning = { policy: policy(learning.policy, out.runtime.observationSize), key: text(learning.key, 50000, "정책의 규칙"), seconds: optionalNumber(learning.seconds, "학습 시간") };
      out.learning.source = learning.source === undefined ? '불러온 정책' : text(learning.source,200,'정책 준비 방식');
    }
    out.results = results(value.results);
    return { project: out, legacy: false };
  }
  function encode(snapshot) {
    var data = normalize(snapshot).project;
    return limitedText(JSON.stringify(data, null, 2));
  }
  function decode(source) {
    limitedText(source);
    var data;
    try { data = JSON.parse(source.replace(/^\uFEFF/, "")); }
    catch (e) { fail("파일 내용을 읽을 수 없습니다. JSON 형식의 수업 프로젝트인지 확인해 주세요."); }
    return normalize(data);
  }
  function filename(name) {
    var base = String(name || "수업 프로젝트").replace(/[<>:"/\\|?*\u0000-\u001f\u007f]/g, "_")
      .replace(/(?:\.(?:pendulum|json))+$/i, "").trim().replace(/[. ]+$/, "").slice(0, 120).replace(/[. ]+$/, "");
    if (!base) base = "수업 프로젝트";
    if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(base)) base = "_" + base;
    return base + ".pendulum";
  }

  PS.Project = {
    EXTENSION: ".pendulum", MAX_BYTES: MAX_BYTES, runtime: runtime, sameRuntime: sameRuntime,
    capturePolicy: capturePolicy, encode: encode, decode: decode, filename: filename
  };
})(window.PS = window.PS || {});
