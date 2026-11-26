/* 블록 편집기 — 엔트리와 같은 모양과 조립 방식.
 *
 * 블록은 DOM 안에 그대로 중첩해 놓아 자리가 저절로 잡히게 하고, 모양(V 홈, 반원 끝, 모자의 원, 육각)은
 * 자리가 잡힌 뒤 크기를 재서 블록마다 SVG 경로로 그립니다(decorate). 치수는 엔트리 편집기의 블록 경로와 같습니다.
 *   쌓기 블록  M0 0 l6 6 l6 -6 H(W-r) a r r 0 0 1 0 H  H12 l-6 6 l-6 -6 z        (높이 28, r = 높이/2)
 *   모자 블록  왼쪽에 반지름 17 원, 몸통 높이 28, 아래 블록은 12 들여서 붙음
 *   감싸는 블록 위 막대 28 + 안쪽(들여쓰기 14) + 아래 막대 15
 *   판단 블록  육각, 끝 폭 = 높이 x 0.4
 *
 * 모델
 *   B[id]          = { id, type, s: [{ block, v }], f: { 고르는 칸 }, bodies: [[id...]] }
 *   scripts.reward = [쌓기 블록 id, ...]   매 순간 점수 매기기
 *   scripts.run    = [쌓기 블록 id, ...]   시작하기 버튼을 클릭했을 때
 *   pos            = { reward, run }       모자 블록 묶음의 자리 ({x, y}). null 이면 위에서부터 차례로 놓음
 *   loose          = [{ lid, x, y, ids }]  조립소에 따로 놓아 둔 블록 묶음. 모자 블록에 붙지 않았으므로 실행되지 않음
 * 따라 하기에서는 고정된 블록 묶음(guide)을 보여 주고, 고르는 칸만 바꿀 수 있습니다.
 */
(function (PS) {
  "use strict";

  var DEFS = PS.DEFS, HATS = PS.HATS, PALETTE = PS.PALETTE, CATS = PS.CATS;
  var NS = "http://www.w3.org/2000/svg";

  function Blocks(container, paletteEl, railEl, opt) {
    opt = opt || {};
    var self = this;
    var M = null, G = null, mode = "free";
    var cat = "score", locked = false, drag = null, pending = null;
    var selected = null, searchText = "", drafts = {}, lastCheck = null, checkKey = "";
    var toolbar = document.createElement("div");
    toolbar.className = "block-tools";
    toolbar.innerHTML = '<div class="block-target" role="status" aria-live="polite">블록을 누르면 설명을 볼 수 있어요.</div><div class="block-tool-actions"><button data-tool="reward">점수 끝 선택</button><button data-tool="run">시작 끝 선택</button><button data-tool="copy">선택 복사</button><button data-tool="delete">선택 삭제</button><button data-tool="tidy">줄 맞추기</button><button data-tool="undo">되돌리기</button></div>';
    container.appendChild(toolbar);

    var board = document.createElement("div");
    board.className = "board";
    var canvas = document.createElement("div");
    canvas.className = "canvas";
    board.appendChild(canvas);
    var ghost = document.createElement("div");
    ghost.className = "ghost";
    ghost.hidden = true;
    board.appendChild(ghost);
    var checkEl = document.createElement("div");
    checkEl.className = "rulecheck";
    container.appendChild(checkEl);
    var notice = document.createElement("div");
    notice.className = "block-notice";
    notice.setAttribute("role", "status");
    notice.setAttribute("aria-live", "polite");
    notice.textContent = "끌어서 연결하거나, 칸을 선택한 뒤 꾸러미의 ‘추가’를 누르세요.";
    container.appendChild(notice);
    var trash = document.createElement("div");
    trash.className = "trash";
    trash.innerHTML = '<svg width="40" height="48" viewBox="0 0 46 56" aria-hidden="true"><rect x="6" y="14" width="34" height="38" rx="5" fill="#dfe8f0" stroke="#aebfce" stroke-width="2"/><rect x="2" y="7" width="42" height="7" rx="3.5" fill="#c7d5e2" stroke="#aebfce" stroke-width="2"/><rect x="17" y="2" width="12" height="6" rx="2" fill="#c7d5e2" stroke="#aebfce" stroke-width="2"/><path d="M15 22v22M23 22v22M31 22v22" stroke="#aebfce" stroke-width="2.4" stroke-linecap="round"/></svg>';
    trash.title = "여기로 끌면 버립니다";
    container.appendChild(trash);
    container.appendChild(board);
    self.board = board;

    var zoom = 1, hist = [], hpos = -1;
    var zoomer = document.createElement("div");
    zoomer.className = "zoomer";
    zoomer.innerHTML = '<button data-z="out" title="작게" aria-label="작게">−</button><button data-z="reset" title="원래 크기"><b>100%</b></button><button data-z="in" title="크게" aria-label="크게">＋</button>';
    container.appendChild(zoomer);

    function cur() { return mode === "guide" ? G : M; }
    function changed(noCommit) {
      if (mode === "free" && !noCommit) commit();
      if (opt.onChange) opt.onChange();
      selectionUI();
    }
    function announce(text) { notice.textContent = text; }
    function inputIssues() {
      return Object.keys(drafts).filter(function (key) { return drafts[key].error && M.B[drafts[key].id]; }).map(function (key) {
        var a = drafts[key];
        return { level: "error", code: "number-input", id: a.id, slot: a.index, message: a.error };
      });
    }
    function selectionUI() {
      canvas.querySelectorAll(".is-selected").forEach(function (el) { el.classList.remove("is-selected"); });
      var el = null, label = "블록을 누르면 설명을 볼 수 있어요.";
      if (selected && selected.kind === "slot" && M.B[selected.parent]) {
        el = canvas.querySelector('.slot[data-parent="' + selected.parent + '"][data-index="' + selected.index + '"]');
        label = (selected.slotKind === "bool" ? "판단 칸" : "숫자 칸") + " 선택 · 꾸러미에서 맞는 블록을 추가하세요.";
      } else if (selected && selected.kind === "block" && M.B[selected.id]) {
        el = canvas.querySelector('.block[data-id="' + selected.id + '"]');
        label = (DEFS[M.B[selected.id].type].name || PS.reward.blockText(M, selected.id)) + " 선택";
      } else if (selected && selected.kind === "list") {
        el = canvas.querySelector('.list[data-list="' + selected.key + '"]');
        label = (selected.key === "script:run" ? "시작 순서 끝" : selected.key === "script:reward" ? "점수 규칙 끝" : "선택한 조건의 안쪽") + "에 추가합니다.";
      }
      if (el) el.classList.add("is-selected");
      toolbar.querySelector(".block-target").textContent = mode === "guide" ? "따라 하기 · 고르는 칸만 바꿔 보세요." : label;
      toolbar.querySelectorAll("button").forEach(function (b) {
        b.disabled = locked || mode === "guide" || ((b.dataset.tool === "copy" || b.dataset.tool === "delete") && (!selected || selected.kind !== "block" || !M.B[selected.id])) || (b.dataset.tool === "undo" && hpos <= 0 && !Object.keys(drafts).length);
      });
    }
    function selectBlock(el) {
      selected = { kind: "block", id: +el.dataset.id };
      pick(el.dataset.type, null, selected.id);
      selectionUI();
    }
    function keepLoose(ids) {
      var y = 26;
      Array.prototype.forEach.call(canvas.children, function (el) { y = Math.max(y, el.offsetTop + el.offsetHeight + 30); });
      M.loose.push({ lid: M.next++, x: Math.max(26, Math.round(board.scrollLeft / zoom) + 26), y: y, ids: ids });
    }

    /* ── 모델 ── */
    function fresh() { return { B: {}, scripts: { reward: [], run: [] }, pos: { reward: null, run: null }, loose: [], next: 1 }; }
    function mkIn(model, type) {
      var d = DEFS[type];
      var b = { id: model.next++, type: type, s: [], f: {}, bodies: [] };
      d.tpl.forEach(function (p) {
        if (typeof p === "string") return;
        if (p.s) b.s.push({ block: null, v: p.v === undefined ? 0 : p.v });
        else if (p.dd) b.f[p.dd] = p.opts[0][0];
      });
      for (var i = 0; i < (d.bodies || 0); i++) b.bodies.push([]);
      model.B[b.id] = b;
      return b;
    }
    function mk(type) { return mkIn(M, type); }

    /* 예시 규칙·기본 블록을 적는 짧은 표기: 숫자 또는 { t, a: [칸...], f: {}, body: [[...]] } */
    function build(model, node) {
      var b = mkIn(model, node.t);
      (node.a || []).forEach(function (arg, i) {
        if (!b.s[i]) return;
        if (typeof arg === "number") b.s[i].v = arg;
        else if (arg) b.s[i].block = build(model, arg);
      });
      if (node.f) for (var k in node.f) b.f[k] = node.f[k];
      (node.body || []).forEach(function (list, i) {
        if (b.bodies[i]) b.bodies[i] = list.map(function (n) { return build(model, n); });
      });
      return b.id;
    }
    var DEFAULT_REWARD = [
      { t: "plus", a: [{ t: "height" }] },
      { t: "if", a: [{ t: "upright" }], body: [[{ t: "plus", a: [50] }]] },
      { t: "minus", a: [{ t: "mul", a: [{ t: "force" }, 0.5] }] }
    ];
    var DEFAULT_RUN = [
      { t: "cond", a: [24], f: { key: "gens" } },
      { t: "learn" },
      { t: "test", a: [10] }
    ];
    function defaults() {
      M = fresh();
      M.scripts.reward = DEFAULT_REWARD.map(function (n) { return build(M, n); });
      M.scripts.run = DEFAULT_RUN.map(function (n) { return build(M, n); });
    }
    function buildGuide(smooth, effort) {
      G = fresh();
      G.scripts.reward = [
        build(G, { t: "g_up" }),
        build(G, { t: "g_smooth", f: { lv: smooth } }),
        build(G, { t: "g_effort", f: { lv: effort } })
      ];
      G.scripts.run = [build(G, { t: "learn" }), build(G, { t: "test", a: [10] })];
    }

    function drop(id) {
      var b = M.B[id];
      if (!b) return;
      b.s.forEach(function (s) { if (s.block) drop(s.block); });
      b.bodies.forEach(function (list) { list.forEach(drop); });
      delete M.B[id];
      Object.keys(drafts).forEach(function (key) { if (drafts[key].id === id) delete drafts[key]; });
    }
    function looseOf(lid) {
      for (var i = 0; i < M.loose.length; i++) if (M.loose[i].lid === lid) return M.loose[i];
      return null;
    }
    function getList(key) {
      var p = key.split(":");
      if (p[0] === "script") return M.scripts[p[1]];
      if (p[0] === "loose") { var L = looseOf(+p[1]); return L ? L.ids : []; }
      return M.B[+p[1]].bodies[+p[2]];
    }
    function pruneLoose() {
      M.loose = M.loose.filter(function (L) { return L.ids.length > 0; });
    }
    function detach(o) {
      if (!o) return;
      if (o.kind === "slot") M.B[o.parent].s[o.index].block = null;
      else getList(o.key).splice(o.index, 1);
    }
    function attach(o, id) {
      if (o.kind === "slot") {
        var s = M.B[o.parent].s[o.index];
        delete drafts[o.parent + ":" + o.index];
        if (s.block) {
          keepLoose([s.block]);
          announce("기존 블록은 조립소 아래에 따로 보관했습니다. 다시 연결하거나 되돌릴 수 있어요.");
        }
        s.block = id;
      } else {
        var list = getList(o.key);
        list.splice(Math.min(o.index, list.length), 0, id);
      }
    }

    /* ── 그리기 ── */
    function shapeSvg() {
      var s = document.createElementNS(NS, "svg");
      s.setAttribute("class", "shape");
      s.appendChild(document.createElementNS(NS, "path"));
      return s;
    }
    function paintShape(el, c) {
      el.dataset.fill = c.color;
      el.dataset.stroke = c.dark;
    }
    function sizeField(inp) {
      inp.style.width = Math.min(180, Math.max(2, String(inp.value).length + 0.6) * 7 + 10) + "px";
    }
    function numField(slot, preview, b, index) {
      var inp = document.createElement("input");
      inp.type = "text";
      inp.inputMode = "decimal";
      inp.className = "field";
      var key = b.id + ":" + index;
      inp.value = !preview && drafts[key] ? drafts[key].raw : slot.v;
      var spec = PS.numericSpec ? PS.numericSpec(b.type, b.f, index) : null;
      var hint = spec ? spec.name + " · " + spec.min + "~" + spec.max + (spec.integer ? " 정수" : "") : "숫자 · 음수와 소수 사용 가능";
      inp.setAttribute("aria-label", (DEFS[b.type].name || "블록") + " " + (index + 1) + "번째 " + hint);
      inp.title = hint;
      inp.maxLength = 100;
      inp.spellcheck = false;
      if (!preview && drafts[key] && drafts[key].error) inp.setAttribute("aria-invalid", "true");
      inp.disabled = locked || preview || mode === "guide";
      sizeField(inp);
      inp.addEventListener("input", function () {
        var raw = inp.value.trim(), x = Number(raw), error = "";
        if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw) || !Number.isFinite(x)) error = "숫자를 끝까지 입력해 주세요. 빈칸·문자·무한대는 사용할 수 없어요.";
        else if (spec && (x < spec.min || x > spec.max || (spec.integer && !Number.isInteger(x)))) error = hint + " 범위로 입력해 주세요.";
        drafts[key] = { id: b.id, index: index, raw: inp.value, error: error };
        if (!error) slot.v = x;
        inp.setAttribute("aria-invalid", String(!!error));
        sizeField(inp);
        decorate(canvas);
        fitCanvas();
        changed(true);
      });
      inp.addEventListener("focus", function () { selected = { kind: "slot", parent: b.id, index: index, slotKind: "num" }; selectionUI(); if (spec) announce(hint + " · 입력 후 Enter를 누르면 확정합니다."); });
      inp.addEventListener("blur", function () {
        if (preview || !drafts[key]) return;
        if (drafts[key].error) { announce(drafts[key].error); return; }
        delete drafts[key]; inp.value = slot.v; sizeField(inp); changed();
      });
      inp.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
        if (e.key === "Escape") {
          e.preventDefault(); e.stopPropagation();
          var old = hist[hpos] ? JSON.parse(hist[hpos]) : null;
          if (old && old.B[b.id] && old.B[b.id].s[index]) slot.v = old.B[b.id].s[index].v;
          delete drafts[key]; inp.value = slot.v; inp.removeAttribute("aria-invalid"); sizeField(inp); changed(); inp.blur();
        }
      });
      inp.addEventListener("pointerdown", function (e) { e.stopPropagation(); });
      return inp;
    }
    function ddField(b, p, c, preview) {
      var sel = document.createElement("select");
      sel.className = "dd";
      sel.style.background = c.dark;
      sel.setAttribute("aria-label", "고르기");
      p.opts.forEach(function (o) {
        var e = document.createElement("option");
        e.value = String(o[0]);
        e.textContent = o[1];
        sel.appendChild(e);
      });
      sel.value = String(b.f[p.dd]);
      sel.disabled = locked || preview;
      var fit = function () {
        var o = sel.options[sel.selectedIndex];
        sel.style.width = ((o ? o.textContent.length : 2) * 11 + 26) + "px";
      };
      fit();
      sel.addEventListener("change", function () {
        var raw = sel.value, n = Number(raw);
        b.f[p.dd] = raw !== "" && !isNaN(n) ? n : raw;
        if (b.type === "cond" && p.dd === "key" && !b.s[0].block && PS.RUN_PARAMS) {
          b.s[0].v = PS.RUN_PARAMS[b.f.key].defaultValue;
          delete drafts[b.id + ":0"];
          announce("학습 조건을 바꾸어 해당 조건의 기본값을 넣었습니다. 원하는 값으로 조절하세요.");
        }
        fit();
        if (mode === "guide" && opt.onGuide) opt.onGuide(b.type, b.f[p.dd]);
        decorate(canvas);
        changed();
        if (b.type === "cond") render();
      });
      sel.addEventListener("pointerdown", function (e) { e.stopPropagation(); });
      var w = document.createElement("span");
      w.className = "ddw";
      w.appendChild(sel);
      return w;
    }
    function fillContent(el, b, model, preview) {
      var d = DEFS[b.type], c = PS.catOf(d.cat), k = 0;
      d.tpl.forEach(function (p) {
        if (typeof p === "string") {
          var t = document.createElement("span");
          t.className = "lbl";
          t.textContent = p;
          el.appendChild(t);
        } else if (p.s) {
          var slot = b.s[k], sp = document.createElement("span");
          sp.className = "slot " + p.s;
          sp.dataset.kind = p.s;
          if (!preview) { sp.dataset.parent = b.id; sp.dataset.index = k; }
          if (slot.block && model.B[slot.block]) sp.appendChild(blockEl(slot.block, model, preview));
          else if (p.s === "num") sp.appendChild(numField(slot, preview, b, k));
          else { var ph = document.createElement("span"); ph.className = "boolph"; ph.textContent = "조건"; sp.appendChild(ph); }
          if (!preview) {
            sp.tabIndex = 0; sp.setAttribute("role", "group");
            sp.setAttribute("aria-label", (p.s === "bool" ? "판단 블록을 넣는 조건 칸" : "값 블록 또는 숫자를 넣는 칸") + " · Enter로 선택");
          }
          el.appendChild(sp);
          k++;
        } else if (p.dd) {
          el.appendChild(ddField(b, p, c, preview));
        }
      });
      if (d.shape === "stk" || d.shape === "c") {
        var ic = document.createElement("span");
        ic.className = "bicon";
        ic.innerHTML = PS.iconSvg(c.key);
        el.appendChild(ic);
      }
    }
    function blockEl(id, model, preview) {
      var b = model.B[id], d = DEFS[b.type], c = PS.catOf(d.cat), el;
      if (d.shape === "val") {
        el = document.createElement("span");
        el.className = "block val";
        el.style.background = c.color;
        el.style.borderColor = c.dark;
        fillContent(el, b, model, preview);
      } else if (d.shape === "bool") {
        el = document.createElement("span");
        el.className = "block bool";
        el.dataset.shape = "bool";
        paintShape(el, c);
        el.appendChild(shapeSvg());
        fillContent(el, b, model, preview);
      } else if (d.shape === "stk") {
        el = document.createElement("div");
        el.className = "block stk";
        el.dataset.shape = "stk";
        paintShape(el, c);
        el.appendChild(shapeSvg());
        fillContent(el, b, model, preview);
        var lv = document.createElement("span");
        lv.className = "live";
        lv.hidden = true;
        el.appendChild(lv);
      } else {
        el = document.createElement("div");
        el.className = "block c";
        el.dataset.shape = "c";
        paintShape(el, c);
        el.appendChild(shapeSvg());
        var head = document.createElement("div");
        head.className = "chead";
        fillContent(head, b, model, preview);
        el.appendChild(head);
        b.bodies.forEach(function (list, i) {
          if (i > 0) {
            var mid = document.createElement("div");
            mid.className = "cmid";
            mid.textContent = d.mid || "";
            el.appendChild(mid);
          }
          var body = preview ? document.createElement("div") : listEl("body:" + b.id + ":" + i, list, d.dom, model);
          body.classList.add("cbody");
          el.appendChild(body);
        });
        var foot = document.createElement("div");
        foot.className = "cfoot";
        el.appendChild(foot);
      }
      el.dataset.id = id;
      el.dataset.type = b.type;
      if (!preview) { el.tabIndex = 0; el.setAttribute("role", "group"); el.setAttribute("aria-label", (d.name || PS.reward.blockText(model, id)) + " · Enter로 선택, Delete로 이 블록 삭제"); }
      if (d.tip) el.title = d.tip;
      return el;
    }
    function gapEl(key, index, dom) {
      var g = document.createElement("div");
      g.className = "gap";
      g.dataset.list = key;
      g.dataset.index = index;
      g.dataset.dom = dom;
      return g;
    }
    function listEl(key, list, dom, model) {
      var col = document.createElement("div");
      col.className = "list";
      col.dataset.list = key;
      col.dataset.dom = dom;
      col.appendChild(gapEl(key, 0, dom));
      list.forEach(function (id, i) {
        if (!model.B[id]) return;
        col.appendChild(blockEl(id, model, false));
        col.appendChild(gapEl(key, i + 1, dom));
      });
      if (key.indexOf("body:") === 0 && mode === "free") {
        var into = document.createElement("button");
        into.className = "body-target"; into.dataset.into = key;
        into.textContent = "＋ 이 안쪽에 추가"; into.disabled = locked;
        col.appendChild(into);
      }
      return col;
    }
    function hatEl(name) {
      var h = HATS[name], c = PS.catOf(h.cat);
      var el = document.createElement("div");
      el.className = "hatb";
      el.dataset.shape = "hat";
      el.dataset.hat = name;
      paintShape(el, c);
      el.appendChild(shapeSvg());
      var ic = document.createElement("span");
      ic.className = "hicon";
      ic.style.color = c.color;
      ic.innerHTML = PS.iconSvg(c.key);
      el.appendChild(ic);
      var t = document.createElement("span");
      t.className = "lbl";
      t.textContent = h.label;
      el.appendChild(t);
      el.title = h.tip;
      return el;
    }
    function scriptEl(name, model) {
      var wrap = document.createElement("div");
      wrap.className = "script";
      wrap.appendChild(hatEl(name));
      var under = listEl("script:" + name, model.scripts[name], mode === "guide" ? "guide" : name, model);
      under.classList.add("under");
      if (!model.scripts[name].length) {
        var e = document.createElement("div");
        e.className = "empty";
        e.textContent = "여기에 블록을 끌어다 붙이세요";
        under.appendChild(e);
      }
      wrap.appendChild(under);
      return wrap;
    }

    function pathFor(el) {
      var kind = el.dataset.shape, W = el.offsetWidth, H = el.offsetHeight, r, d;
      if (kind === "stk") {
        r = H / 2;
        d = "M0 0 l6 6 l6 -6 H" + (W - r) + " a" + r + " " + r + " 0 0 1 0 " + H + " H12 l-6 6 l-6 -6 z";
        return { d: d, w: W, h: H + 7 };
      }
      if (kind === "hat") {
        d = "M24 34 H" + (W - 14) + " a14 14 0 0 0 0 -28 H30 A17 17 0 0 0 18 1 C8.611 1 1 8.611 1 18 c0 7.2 4.5 13.5 11 16 l6 6 l6 -6 z";
        return { d: d, w: W, h: 41 };
      }
      if (kind === "bool") {
        var e = 0.4 * H;
        d = "M" + e + " 0 L0 " + (H / 2) + " L" + e + " " + H + " H" + (W - e) + " L" + W + " " + (H / 2) + " L" + (W - e) + " 0 z";
        return { d: d, w: W, h: H };
      }
      var head = el.querySelector(":scope > .chead");
      var bodies = el.querySelectorAll(":scope > .cbody"), mids = el.querySelectorAll(":scope > .cmid");
      var hw = head.offsetWidth, hh = head.offsetHeight;
      r = hh / 2;
      d = "M0 0 l6 6 l6 -6 H" + (hw - r) + " a" + r + " " + r + " 0 0 1 0 " + hh + " H26 l-6 6 l-6 -6";
      for (var i = 0; i < bodies.length; i++) {
        d += " v" + bodies[i].offsetHeight + " l6 6 l6 -6";
        if (i < bodies.length - 1) {
          var mh = mids[i] ? mids[i].offsetHeight : 28;
          d += " H" + (hw - 22) + " a" + (mh / 2) + " " + (mh / 2) + " 0 0 1 0 " + mh + " H26 l-6 6 l-6 -6";
        }
      }
      d += " H" + (hw - 22) + " a7.5 7.5 0 0 1 0 15 H12 l-6 6 l-6 -6 z";
      return { d: d, w: hw, h: H + 7 };
    }
    function decorate(root) {
      var list = root.querySelectorAll("[data-shape]");
      for (var i = 0; i < list.length; i++) {
        var el = list[i], svg = el.firstElementChild;
        if (!svg || !el.offsetWidth) continue;
        var p = pathFor(el), path = svg.firstChild;
        path.setAttribute("d", p.d);
        path.setAttribute("fill", el.dataset.fill);
        path.setAttribute("stroke", el.dataset.stroke);
        svg.setAttribute("width", p.w + 2);
        svg.setAttribute("height", p.h + 2);
      }
    }

    /* 따로 놓아 둔 묶음. 쌓기 블록이면 사이에 끼울 수 있는 목록, 값·판단 블록이면 블록 하나. */
    function looseEl(L, model) {
      var wrap = document.createElement("div");
      wrap.className = "script loose";
      wrap.title = "모자 블록에 붙어 있지 않아 실행되지 않습니다";
      var badge = document.createElement("span"); badge.className = "loose-label"; badge.textContent = "연결 전 · 실행 제외"; wrap.appendChild(badge);
      var first = L.ids.length ? DEFS[model.B[L.ids[0]].type] : null, col;
      if (first && (first.shape === "val" || first.shape === "bool")) {
        col = document.createElement("div");
        col.className = "list";
        col.dataset.list = "loose:" + L.lid;
        col.appendChild(blockEl(L.ids[0], model, false));
      } else {
        col = listEl("loose:" + L.lid, L.ids, first ? first.dom : "*", model);
      }
      wrap.appendChild(col);
      return wrap;
    }
    function place(el, x, y) {
      el.style.left = x + "px";
      el.style.top = y + "px";
    }
    function fitCanvas() {
      var w = 0, h = 0, kids = canvas.children;
      for (var i = 0; i < kids.length; i++) {
        w = Math.max(w, kids[i].offsetLeft + kids[i].offsetWidth);
        h = Math.max(h, kids[i].offsetTop + kids[i].offsetHeight);
      }
      canvas.style.width = (w + 80) + "px";
      canvas.style.height = (h + 90) + "px";
    }
    function render() {
      pending = null;
      var model = cur(), pos = model.pos || {};
      canvas.innerHTML = "";
      var a = scriptEl("reward", model);
      canvas.appendChild(a);
      var pa = pos.reward || { x: 26, y: 22 };
      place(a, pa.x, pa.y);
      var b = scriptEl("run", model);
      canvas.appendChild(b);
      var pb = pos.run || { x: pa.x, y: pa.y + a.offsetHeight + 34 };
      place(b, pb.x, pb.y);
      (model.loose || []).forEach(function (L) {
        var e = looseEl(L, model);
        canvas.appendChild(e);
        place(e, L.x, L.y);
      });
      board.classList.toggle("guided", mode === "guide");
      fitCanvas();
      decorate(canvas);
      selectionUI();
      highlightIssues();
    }

    /* ── 꾸러미(팔레트) ── */
    function paint() {
      paletteEl.innerHTML = "";
      var c = PS.catOf(cat);
      railEl.querySelectorAll("button").forEach(function (b) {
        var on = b.dataset.cat === cat, cc = PS.catOf(b.dataset.cat);
        b.setAttribute("aria-pressed", String(on));
        b.style.background = on ? cc.color : "";
        b.querySelector("i").style.background = on ? "#fff" : cc.color;
        b.querySelector("i").style.color = on ? cc.color : "#fff";
      });
      if (mode === "guide") {
        var n = document.createElement("p");
        n.className = "palnote";
        n.textContent = "따라 하기에서는 블록이 정해져 있어요. 블록 안의 고르는 칸(▼)만 바꿔 보세요. " +
          "블록을 직접 쌓으려면 위에서 '자유롭게 만들기'를 누르세요.";
        paletteEl.appendChild(n);
        return;
      }
      var search = document.createElement("input");
      search.type = "search"; search.className = "block-search"; search.placeholder = "블록 찾기 · 각도, 이하, 점수…";
      search.setAttribute("aria-label", "모든 범주에서 블록 찾기"); search.value = searchText;
      var composing = false;
      function searchBlocks() {
        searchText = search.value; var caret = search.selectionStart; paint();
        var next = paletteEl.querySelector(".block-search"); next.focus();
        try { next.setSelectionRange(caret, caret); } catch (_) { }
      }
      search.addEventListener("compositionstart", function () { composing = true; });
      search.addEventListener("compositionend", function () { composing = false; searchBlocks(); });
      search.addEventListener("input", function (e) { if (!composing && !e.isComposing) searchBlocks(); });
      paletteEl.appendChild(search);
      var how = document.createElement("p"); how.className = "palette-how";
      how.textContent = "블록을 끌거나 ‘추가’를 누르세요. 숫자 칸과 육각 조건 칸은 모양이 달라요.";
      paletteEl.appendChild(how);
      var tmp = fresh(), lastGroup = null;
      if (cat === "start" && !searchText.trim()) {
        var note = document.createElement("p");
        note.className = "palnote";
        note.textContent = "시작 블록 두 개는 조립소에 이미 놓여 있습니다. 그 아래에 다른 블록을 붙이세요.";
        paletteEl.appendChild(note);
        ["reward", "run"].forEach(function (name) {
          var row = document.createElement("div");
          row.className = "palrow hatrow";
          row.appendChild(hatEl(name));
          paletteEl.appendChild(row);
        });
      }
      var types = searchText.trim() ? CATS.reduce(function (all, cc) { return all.concat(PALETTE[cc.key]); }, []) : PALETTE[cat];
      var terms = searchText.toLowerCase().trim().split(/\s+/).filter(Boolean), found = 0;
      types.forEach(function (type) {
        var d = DEFS[type];
        var words = (type + " " + (d.name || "") + " " + (d.search || "") + " " + (d.tip || "") + " " + d.tpl.filter(function (p) { return typeof p === "string"; }).join(" ")).toLowerCase();
        if (!terms.every(function (term) { return words.indexOf(term) !== -1; })) return;
        found++;
        var cc = PS.catOf(d.cat), group = d.group || cc.name + " · " + cc.note;
        if (group !== lastGroup) {
          var h = document.createElement("h3");
          h.textContent = group;
          paletteEl.appendChild(h);
          lastGroup = group;
        }
        var b = mkIn(tmp, type);
        var row = document.createElement("div");
        row.className = "palrow";
        var el = blockEl(b.id, tmp, true);
        el.classList.add("palblock");
        el.dataset.new = type;
        el.tabIndex = 0; el.setAttribute("role", "button"); el.setAttribute("aria-label", (d.name || PS.reward.blockText(tmp, b.id)) + " · Enter로 추가");
        var preview = document.createElement("div"); preview.className = "palpreview"; preview.appendChild(el); row.appendChild(preview);
        var actions = document.createElement("div"); actions.className = "pal-actions";
        var add = document.createElement("button"); add.dataset.add = type; add.textContent = "＋ 추가"; add.disabled = locked;
        add.setAttribute("aria-label", (d.name || type) + " 블록 추가"); actions.appendChild(add);
        var desc = document.createElement("details"); var summary = document.createElement("summary"); summary.textContent = "설명"; desc.appendChild(summary);
        var tip = document.createElement("p"); tip.textContent = d.tip || ""; desc.appendChild(tip); actions.appendChild(desc); row.appendChild(actions);
        paletteEl.appendChild(row);
      });
      if (!found && terms.length) { var empty = document.createElement("p"); empty.className = "palnote"; empty.textContent = "찾은 블록이 없어요. ‘각도’, ‘조건’, ‘범위’처럼 짧게 찾아보세요."; paletteEl.appendChild(empty); }
      var r = document.createElement("button");
      r.className = "reset";
      r.textContent = "처음 블록으로 되돌리기";
      r.disabled = locked;
      r.addEventListener("click", function () { cancelDrag(); drafts = {}; selected = null; defaults(); render(); changed(); announce("처음 블록으로 바꿨습니다. ‘되돌리기’로 이전 작업을 복구할 수 있어요."); });
      paletteEl.appendChild(r);
      decorate(paletteEl);
    }

    railEl.innerHTML = "";
    CATS.forEach(function (c) {
      var b = document.createElement("button");
      b.dataset.cat = c.key;
      b.innerHTML = "<i></i><span></span>";
      b.querySelector("i").innerHTML = PS.iconSvg(c.key);
      b.querySelector("span").textContent = c.name;
      b.addEventListener("click", function () { cancelDrag(); cat = c.key; searchText = ""; paint(); });
      railEl.appendChild(b);
    });

    /* ── 끌어 놓기 ──
     * 쌓기 블록을 끌면 엔트리처럼 그 아래에 붙은 블록도 함께 움직입니다(drag.ids). */
    function originOf(el) {
      var id = +el.dataset.id, p = el.parentNode;
      if (p && p.classList.contains("slot")) return { kind: "slot", parent: +p.dataset.parent, index: +p.dataset.index, id: id };
      if (p && p.classList.contains("list")) {
        var list = getList(p.dataset.list);
        return { kind: "list", key: p.dataset.list, index: list.indexOf(id), id: id };
      }
      return null;
    }
    function ghostFrom(ids) {
      ghost.innerHTML = "";
      var col = document.createElement("div");
      col.className = "list";
      ids.forEach(function (id) { col.appendChild(blockEl(id, M, false)); });
      ghost.appendChild(col);
      ghost.hidden = false;
      ghost.style.transform = "scale(" + zoom + ")";
      decorate(ghost);
    }
    function clearTargets() {
      board.querySelectorAll(".over").forEach(function (e) { e.classList.remove("over"); });
    }
    function findSlot(x, y, kind) {
      var list = document.elementsFromPoint(x, y);
      for (var i = 0; i < list.length; i++) {
        var e = list[i];
        if (ghost.contains(e) || !canvas.contains(e)) continue;
        if (e.classList && e.classList.contains("slot") && e.dataset.kind === kind && e.dataset.parent) return e;
      }
      return null;
    }
    function findGap(x, y, dom) {
      var gaps = canvas.querySelectorAll(".gap"), best = null, bestScore = 1e9;
      for (var i = 0; i < gaps.length; i++) {
        var g = gaps[i];
        if (g.dataset.dom !== dom && g.dataset.dom !== "*") continue;
        var r = g.getBoundingClientRect();
        var dy = Math.abs(y - r.top), dx = x - r.left;
        if (dy > 22 * zoom || dx < -40 * zoom || dx > 300 * zoom) continue;
        var score = dy - r.left * 0.001;
        if (score < bestScore) { bestScore = score; best = g; }
      }
      return best;
    }
    function targetFor(x, y) {
      if (!drag) return null;
      if (drag.shape === "val") return findSlot(x, y, "num");
      if (drag.shape === "bool") return findSlot(x, y, "bool");
      return findGap(x, y, drag.dom);
    }
    function pick(type, hat, currentId) {
      if (!opt.onPick) return;
      if (hat) { opt.onPick(HATS[hat].label, HATS[hat].tip); return; }
      var d = DEFS[type];
      var tmp = fresh(), b = mkIn(tmp, type);
      var model = cur();
      opt.onPick(currentId && model.B[currentId] ? PS.reward.blockText(model, currentId) : PS.reward.blockText(tmp, b.id), d.tip || "");
    }
    function insertAt(key, index, ids) {
      var list = getList(key);
      Array.prototype.splice.apply(list, [Math.min(index, list.length), 0].concat(ids));
    }
    function putBack() {
      if (!drag) return;
      if (!drag.origin) { drag.ids.forEach(drop); return; }
      if (drag.origin.kind === "slot") attach(drag.origin, drag.ids[0]);
      else insertAt(drag.origin.key, drag.origin.index, drag.ids);
    }

    /* Dragging is optional: a selected slot/body plus Add also assembles a program. */
    function addBlock(type) {
      if (locked || mode !== "free" || drag || !DEFS[type]) return;
      if (Object.keys(M.B).length >= 1000) { announce("블록은 1,000개까지 사용할 수 있어요."); return; }
      var d = DEFS[type], dest = selected, b = mk(type), placed = false;
      if (dest && dest.kind === "slot" && M.B[dest.parent]) {
        if (d.shape === (dest.slotKind === "bool" ? "bool" : "val")) { attach(dest, b.id); placed = true; }
        else { drop(b.id); announce("선택한 칸과 블록 모양이 달라요. 숫자 칸에는 둥근 값, 조건 칸에는 육각 판단 블록을 넣으세요."); return; }
      } else if (d.shape === "stk" || d.shape === "c") {
        var key = "script:" + d.dom, at = getList(key).length;
        if (dest && dest.kind === "list") {
          var col = canvas.querySelector('.list[data-list="' + dest.key + '"]');
          if (col && col.dataset.dom === d.dom) { key = dest.key; at = getList(key).length; }
          else { drop(b.id); announce("이 블록은 " + (d.dom === "run" ? "시작하기" : "점수 규칙") + " 묶음에 넣어 주세요."); return; }
        } else if (dest && dest.kind === "block") {
          var el = canvas.querySelector('.block[data-id="' + dest.id + '"]'), o = el && originOf(el);
          if (o && o.kind === "list" && DEFS[M.B[dest.id].type].dom === d.dom) { key = o.key; at = o.index + 1; }
        }
        insertAt(key, at, [b.id]); placed = true;
      }
      if (!placed) keepLoose([b.id]);
      selected = { kind: "block", id: b.id }; render(); changed(); focusIssue({ id: b.id });
      announce(placed ? "블록을 추가했습니다. 숫자와 조건을 살펴보세요." : "값 블록을 따로 두었습니다. 넣을 칸을 선택한 뒤 ‘추가’를 쓰거나 이 블록을 끌어 연결하세요.");
    }
    function cloneBlock(id) {
      var src = M.B[id], dst = mk(src.type);
      dst.f = Object.assign({}, src.f);
      dst.s = src.s.map(function (s) { return { v: s.v, block: s.block ? cloneBlock(s.block) : null }; });
      dst.bodies = src.bodies.map(function (list) { return list.map(cloneBlock); });
      return dst.id;
    }
    function subtreeSize(id, seen) {
      seen = seen || {}; if (seen[id] || !M.B[id]) return 0; seen[id] = true;
      var b = M.B[id], n = 1;
      b.s.forEach(function (s) { if (s.block) n += subtreeSize(s.block, seen); });
      b.bodies.forEach(function (list) { list.forEach(function (child) { n += subtreeSize(child, seen); }); });
      return n;
    }
    function editSelected(copy) {
      if (locked || mode !== "free" || drag || !selected || selected.kind !== "block" || !M.B[selected.id]) return;
      var id = selected.id, el = canvas.querySelector('.block[data-id="' + id + '"]'), o = el && originOf(el);
      if (!o) return;
      if (copy) {
        if (Object.keys(M.B).length + subtreeSize(id) > 1000) { announce("복사하면 1,000개를 넘어요. 쓰지 않는 블록을 먼저 정리하세요."); return; }
        var duplicate = cloneBlock(id);
        if (o.kind === "list" && (DEFS[M.B[id].type].shape === "stk" || DEFS[M.B[id].type].shape === "c")) insertAt(o.key, o.index + 1, [duplicate]);
        else keepLoose([duplicate]);
        selected = { kind: "block", id: duplicate };
      } else { detach(o); drop(id); selected = null; }
      pruneLoose(); render(); changed();
      if (copy) focusIssue({ id: selected.id });
      announce(copy ? "선택한 블록과 그 안쪽을 복사했습니다." : "선택한 블록과 그 안쪽을 삭제했습니다. 뒤에 이어진 블록은 남습니다. ‘되돌리기’로 복구할 수 있어요.");
    }
    toolbar.addEventListener("click", function (e) {
      var button = e.target.closest("button"); if (!button || button.disabled || drag) return;
      var action = button.dataset.tool;
      if (action === "reward" || action === "run") { selected = { kind: "list", key: "script:" + action }; selectionUI(); }
      if (action === "copy" || action === "delete") editSelected(action === "copy");
      if (action === "undo") self.undo();
      if (action === "tidy") {
        M.pos = { reward: null, run: null }; render();
        var y = 26; canvas.querySelectorAll(".script:not(.loose)").forEach(function (el) { y = Math.max(y, el.offsetTop + el.offsetHeight + 34); });
        M.loose.forEach(function (L) { L.x = 26; L.y = y; var el = canvas.querySelector('.loose [data-id="' + L.ids[0] + '"]'); y += (el ? el.closest(".script").offsetHeight : 80) + 34; });
        render(); changed(); board.scrollTop = 0; board.scrollLeft = 0; announce("연결은 유지하고 묶음을 세로로 정렬했습니다.");
      }
    });
    board.addEventListener("click", function (e) {
      var b = e.target.closest("[data-into]");
      if (b && !b.disabled) { selected = { kind: "list", key: b.dataset.into }; selectionUI(); announce("이 조건 안쪽을 선택했습니다. 점수 또는 흐름 블록을 추가하세요."); }
    });
    board.addEventListener("keydown", function (e) {
      if (e.target.closest("input,select,button") || locked || mode !== "free") return;
      var slot = e.target.closest(".slot"), el = e.target.closest(".block");
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (e.target.classList.contains("slot")) { selected = { kind: "slot", parent: +slot.dataset.parent, index: +slot.dataset.index, slotKind: slot.dataset.kind }; selectionUI(); }
        else if (el) selectBlock(el);
      } else if (el && !e.target.classList.contains("slot") && (e.key === "Delete" || e.key === "Backspace")) { e.preventDefault(); selectBlock(el); editSelected(false); }
      else if (el && !e.target.classList.contains("slot") && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") { e.preventDefault(); selectBlock(el); editSelected(true); }
    });
    paletteEl.addEventListener("click", function (e) { var b = e.target.closest("[data-add]"); if (b && !b.disabled) addBlock(b.dataset.add); });
    paletteEl.addEventListener("keydown", function (e) {
      if (e.target.classList.contains("palblock") && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); addBlock(e.target.dataset.new); }
    });
    function focusIssue(issue) {
      var el = issue.id ? canvas.querySelector('.block[data-id="' + issue.id + '"]') : null;
      if (el && issue.slot !== undefined) el = canvas.querySelector('.slot[data-parent="' + issue.id + '"][data-index="' + issue.slot + '"]') || el;
      if (!el) return;
      el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" }); el.focus({ preventScroll: true });
    }
    function highlightIssues() {
      canvas.querySelectorAll(".block-error,.slot-error").forEach(function (el) { el.classList.remove("block-error", "slot-error"); });
      if (!lastCheck || mode === "guide") return;
      (lastCheck.issues || []).forEach(function (issue) {
        if (issue.level !== "error" || !issue.id) return;
        var el = canvas.querySelector('.block[data-id="' + issue.id + '"]'); if (el) el.classList.add("block-error");
        if (issue.slot !== undefined) { var slot = canvas.querySelector('.slot[data-parent="' + issue.id + '"][data-index="' + issue.slot + '"]'); if (slot) slot.classList.add("slot-error"); }
      });
    }

    function startBoardDrag(e, el, hat) {
      if (Object.keys(drafts).some(function (key) { return !drafts[key].error; })) commit();
      if (hat) {
        pick(null, hat.dataset.hat);
        if (locked || mode === "guide") return;
        var sc = hat.parentNode, hr = sc.getBoundingClientRect();
        drag = { pointerId: e.pointerId, script: hat.dataset.hat, el: sc, dx: e.clientX - hr.left, dy: e.clientY - hr.top };
        sc.classList.add("moving");
        board.setPointerCapture(e.pointerId);
        e.preventDefault();
        return;
      }
      if (!el) return;
      pick(el.dataset.type);
      if (locked || mode === "guide") return;
      var o = originOf(el);
      if (!o) return;
      var d = DEFS[M.B[o.id].type], r = el.getBoundingClientRect(), ids;
      if (o.kind === "list") ids = getList(o.key).splice(o.index);
      else { ids = [o.id]; detach(o); }
      drag = { pointerId: e.pointerId, ids: ids, origin: o, shape: d.shape, dom: d.dom, dx: e.clientX - r.left, dy: e.clientY - r.top };
      ghostFrom(ids);
      render();
      moveGhost(e.clientX, e.clientY);
      board.setPointerCapture(e.pointerId);
      e.preventDefault();
      markCompatible();
    }

    function startPaletteDrag(e, el) {
      if (!el) return;
      pick(el.dataset.new);
      if (locked || mode === "guide") return;
      if (Object.keys(drafts).some(function (key) { return !drafts[key].error; })) commit();
      if (Object.keys(M.B).length >= 1000) { announce("블록은 1,000개까지 사용할 수 있어요. 쓰지 않는 블록을 정리해 주세요."); return; }
      var type = el.dataset.new, d = DEFS[type];
      var b = mk(type), r = el.getBoundingClientRect();
      drag = { pointerId: e.pointerId, ids: [b.id], origin: null, shape: d.shape, dom: d.dom, dx: (e.clientX - r.left) * zoom, dy: (e.clientY - r.top) * zoom };
      ghostFrom(drag.ids);
      moveGhost(e.clientX, e.clientY);
      paletteEl.setPointerCapture(e.pointerId);
      e.preventDefault();
      markCompatible();
    }
    function markCompatible() {
      if (!drag || drag.script) return;
      var selector = drag.shape === "val" || drag.shape === "bool" ? '.slot[data-kind="' + (drag.shape === "val" ? "num" : "bool") + '"]' : '.gap[data-dom="' + drag.dom + '"]';
      canvas.querySelectorAll(selector).forEach(function (el) { el.classList.add("can-connect"); });
      announce(drag.shape === "val" ? "둥근 숫자 칸에 연결하세요. Esc로 이동을 취소합니다." : drag.shape === "bool" ? "육각 조건 칸에 연결하세요. Esc로 이동을 취소합니다." : (drag.dom === "run" ? "시작하기 아래에 연결하세요." : "매 순간 점수 매기기 또는 조건 안쪽에 연결하세요.") + " Esc로 이동을 취소합니다.");
    }
    board.addEventListener("pointerdown", function (e) {
      if (drag || pending) return;
      if (e.button !== 0 || e.target.closest("input,select,button")) return;
      var slot = e.target.closest(".slot"), el = e.target.closest(".block"), hat = e.target.closest(".hatb");
      if (slot && (!el || !slot.contains(el))) {
        selected = { kind: "slot", parent: +slot.dataset.parent, index: +slot.dataset.index, slotKind: slot.dataset.kind };
        selectionUI(); announce("칸을 선택했습니다. 꾸러미에서 같은 모양의 블록을 ‘추가’하세요."); return;
      }
      if (el) selectBlock(el);
      if (hat) pick(null, hat.dataset.hat);
      if (locked || mode === "guide" || (!el && !hat)) return;
      pending = { event: e, el: el, hat: hat, source: "board", x: e.clientX, y: e.clientY };
      board.setPointerCapture(e.pointerId); e.preventDefault();
    });
    paletteEl.addEventListener("pointerdown", function (e) {
      if (drag || pending) return;
      if (e.button !== 0 || e.target.closest("button,summary,input[type=search]")) return;
      var hat = e.target.closest(".hatb");
      if (hat) { pick(null, hat.dataset.hat); return; }
      var el = e.target.closest(".palblock");
      if (!el) return;
      pick(el.dataset.new);
      if (locked || mode === "guide") return;
      pending = { event: e, el: el, source: "palette", x: e.clientX, y: e.clientY };
      paletteEl.setPointerCapture(e.pointerId); e.preventDefault();
    });

    function moveGhost(x, y) {
      var br = board.getBoundingClientRect();
      ghost.style.left = (x - br.left + board.scrollLeft - drag.dx) + "px";
      ghost.style.top = (y - br.top + board.scrollTop - drag.dy) + "px";
    }
    function overTrash(x, y) {
      var r = trash.getBoundingClientRect();
      return x >= r.left - 10 && x <= r.right + 10 && y >= r.top - 10 && y <= r.bottom + 10;
    }
    function boardXY(x, y) {
      var br = board.getBoundingClientRect();
      return {
        x: Math.max(0, Math.round((x - br.left + board.scrollLeft - drag.dx) / zoom)),
        y: Math.max(0, Math.round((y - br.top + board.scrollTop - drag.dy) / zoom))
      };
    }
    function insideBoard(x, y) {
      var br = board.getBoundingClientRect();
      return x >= br.left && x <= br.right && y >= br.top && y <= br.bottom;
    }
    function onMove(e) {
      if ((pending && pending.event.pointerId !== e.pointerId) || (drag && drag.pointerId !== e.pointerId)) return;
      if (pending) {
        if (Math.hypot(e.clientX - pending.x, e.clientY - pending.y) < 6) return;
        var begin = pending; pending = null;
        if (begin.source === "board") startBoardDrag(begin.event, begin.el, begin.hat);
        else startPaletteDrag(begin.event, begin.el);
      }
      if (!drag) return;
      var bounds = board.getBoundingClientRect();
      if (insideBoard(e.clientX, e.clientY)) {
        if (e.clientY < bounds.top + 28) board.scrollTop -= 14;
        if (e.clientY > bounds.bottom - 45) board.scrollTop += 14;
        if (e.clientX < bounds.left + 28) board.scrollLeft -= 14;
        if (e.clientX > bounds.right - 28) board.scrollLeft += 14;
      }
      if (drag.script) {
        var q = boardXY(e.clientX, e.clientY);
        place(drag.el, q.x, q.y);
        return;
      }
      moveGhost(e.clientX, e.clientY);
      clearTargets();
      var t = targetFor(e.clientX, e.clientY);
      if (t) t.classList.add("over");
      trash.classList.toggle("over", overTrash(e.clientX, e.clientY));
    }
    function onUp(e) {
      if ((pending && pending.event.pointerId !== e.pointerId) || (drag && drag.pointerId !== e.pointerId)) return;
      if (pending) { pending = null; return; }
      if (!drag) return;
      if (drag.script) {
        M.pos[drag.script] = boardXY(e.clientX, e.clientY);
        drag = null;
        render();
        changed();
        return;
      }
      var t = targetFor(e.clientX, e.clientY);
      var away = overTrash(e.clientX, e.clientY);
      var wrong = document.elementsFromPoint(e.clientX, e.clientY).some(function (el) { return canvas.contains(el) && el.classList && el.classList.contains("slot"); });
      clearTargets();
      trash.classList.remove("over");
      ghost.hidden = true;
      ghost.innerHTML = "";
      if (away) {
        drag.ids.forEach(drop);
        announce("끌고 있던 묶음을 삭제했습니다. ‘되돌리기’로 복구할 수 있어요.");
      } else if (t && t.classList.contains("slot")) {
        attach({ kind: "slot", parent: +t.dataset.parent, index: +t.dataset.index }, drag.ids[0]);
      } else if (t) {
        insertAt(t.dataset.list, +t.dataset.index, drag.ids);
        announce("블록을 연결했습니다.");
      } else if (wrong) {
        putBack();
        announce("모양이 맞지 않아 연결하지 않았습니다. 숫자 칸에는 둥근 값, 조건 칸에는 육각 판단 블록을 넣으세요.");
      } else if (insideBoard(e.clientX, e.clientY)) {
        /* 조립소 빈 곳에 놓으면 그 자리에 따로 놓아 둡니다(엔트리와 같음). */
        var q = boardXY(e.clientX, e.clientY);
        M.loose.push({ lid: M.next++, x: q.x, y: q.y, ids: drag.ids });
        announce("따로 놓은 블록은 실행되지 않습니다. 모자 아래나 알맞은 칸에 연결하세요.");
      } else if (drag.origin) {
        putBack();
        announce("조립소 밖에 놓아 원래 자리로 돌렸습니다.");
      } else {
        drag.ids.forEach(drop);
      }
      drag = null;
      pruneLoose();
      render();
      changed();
    }
    board.addEventListener("pointermove", onMove);
    paletteEl.addEventListener("pointermove", onMove);
    board.addEventListener("pointerup", onUp);
    paletteEl.addEventListener("pointerup", onUp);
    function cancelDrag(e) {
      if (e && e.pointerId !== undefined && ((pending && pending.event.pointerId !== e.pointerId) || (drag && drag.pointerId !== e.pointerId))) return;
      pending = null;
      if (!drag) return;
      ghost.hidden = true;
      if (!drag.script) putBack();
      drag = null;
      pruneLoose();
      clearTargets();
      trash.classList.remove("over");
      render();
      announce("이동을 취소하고 원래 자리로 돌렸습니다.");
    }
    window.addEventListener("pointercancel", cancelDrag);
    board.addEventListener("lostpointercapture", cancelDrag);
    paletteEl.addEventListener("lostpointercapture", cancelDrag);
    window.addEventListener("blur", cancelDrag);
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && (pending || drag)) { e.preventDefault(); cancelDrag(); }
    });

    /* ── 되돌리기 / 다시 실행 ── */
    function commit() {
      Object.keys(drafts).forEach(function (key) { if (!drafts[key].error) delete drafts[key]; });
      var now = JSON.stringify(M);
      if (hist[hpos] === now) return;
      hist = hist.slice(0, hpos + 1);
      hist.push(now);
      if (hist.length > 60) hist.shift();
      hpos = hist.length - 1;
    }
    function restore(i) {
      if (i < 0 || i >= hist.length || locked || mode === "guide" || drag) return false;
      hpos = i;
      M = JSON.parse(hist[i]);
      drafts = {}; selected = null;
      render();
      paint();
      if (opt.onChange) opt.onChange();
      announce("이전 편집 상태로 바꿨습니다.");
      return true;
    }

    /* ── 조립소 확대·축소 ── */
    function setZoom(z) {
      zoom = Math.max(0.6, Math.min(2, Math.round(z * 100) / 100));
      canvas.style.transform = "scale(" + zoom + ")";
      zoomer.querySelector("b").textContent = Math.round(zoom * 100) + "%";
      try { localStorage.setItem("ps.zoom", String(zoom)); } catch (err) { return; }
    }
    zoomer.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.z === "out") setZoom(zoom - 0.1);
      else if (b.dataset.z === "in") setZoom(zoom + 0.1);
      else setZoom(1);
    });

    /* ── 바깥에서 쓰는 것 ── */
    self.model = function () { return M; };
    self.mode = function () { return mode; };
    self.setMode = function (m, g) {
      cancelDrag();
      mode = m;
      if (m === "guide") buildGuide(g.smooth, g.effort);
      render();
      paint();
    };
    self.refresh = function () { cancelDrag(); render(); paint(); };
    self.lock = function (on) { cancelDrag(); locked = on; board.classList.toggle("locked", on); render(); paint(); };
    self.rule = function () {
      var r = PS.reward.blocks(M), invalid = inputIssues();
      if (invalid.length) {
        var used = {};
        function visit(id) { if (used[id] || !M.B[id]) return; used[id] = true; M.B[id].s.forEach(function (s) { if (s.block) visit(s.block); }); M.B[id].bodies.forEach(function (list) { list.forEach(visit); }); }
        M.scripts.reward.concat(M.scripts.run).forEach(visit);
        invalid.forEach(function (issue) { if (!used[issue.id]) { issue.level = "warn"; issue.message = "실행 제외 블록 · " + issue.message; } });
        if (invalid.some(function (issue) { return issue.level === "error"; })) r.ok = false;
        r.issues = invalid.concat(r.issues || []);
      }
      return r;
    };
    self.inputIssues = inputIssues;
    self.focusIssue = focusIssue;
    self.runOpts = function () { return PS.reward.runOpts(cur()); };
    self.reset = function () { cancelDrag(); drafts = {}; selected = null; defaults(); render(); paint(); changed(); };
    self.undo = function () { return restore(Object.keys(drafts).length ? hpos : hpos - 1); };
    self.redo = function () { return restore(hpos + 1); };
    self.canUndo = function () { return mode === "free" && (hpos > 0 || Object.keys(drafts).length > 0); };
    self.canRedo = function () { return mode === "free" && hpos < hist.length - 1; };
    self.mark = function (type) {
      canvas.querySelectorAll(".block.running").forEach(function (e) { e.classList.remove("running"); });
      if (!type) return;
      var el = canvas.querySelector('.list[data-list="script:run"] > .block[data-type="' + type + '"]');
      if (el) el.classList.add("running");
    };
    self.loadReward = function (nodes) {
      if (locked) return false;
      cancelDrag();
      var remaining = Object.keys(M.B).length, count = 0;
      M.scripts.reward.forEach(function (id) { remaining -= subtreeSize(id); });
      function countNode(node) {
        count++;
        (node.a || []).forEach(function (value) { if (value && typeof value === "object") countNode(value); });
        (node.body || []).forEach(function (list) { list.forEach(countNode); });
      }
      nodes.forEach(countNode);
      if (remaining + count > 1000) { announce("예시를 넣으면 1,000개를 넘어요. 따로 놓은 블록을 먼저 정리해 주세요."); return false; }
      M.scripts.reward.slice().forEach(drop);
      M.scripts.reward = nodes.map(function (n) { return build(M, n); });
      render();
      changed();
      announce("예시로 점수 규칙을 바꿨습니다. ‘되돌리기’로 이전 규칙을 복구할 수 있어요.");
      return true;
    };
    self.exportModel = function () { return JSON.parse(JSON.stringify(M)); };
    self.importModel = function (o) {
      if (!o || !o.B || !o.scripts || !o.scripts.reward || !o.scripts.run) return false;
      for (var k in o.B) if (!DEFS[o.B[k].type]) return false;
      cancelDrag();
      M = JSON.parse(JSON.stringify(o));
      drafts = {}; selected = null;
      if (!M.pos) M.pos = { reward: null, run: null };
      if (!M.loose) M.loose = [];
      // An opened project starts its own undo history; do not mix two students' work.
      hist = []; hpos = -1; commit();
      render();
      changed();
      return true;
    };
    self.setCheck = function (c) {
      lastCheck = c; highlightIssues();
      var key = JSON.stringify(c);
      if (key === checkKey) return;
      checkKey = key;
      checkEl.className = "rulecheck " + (c ? c.level : "");
      var wasOpen = !!checkEl.querySelector("details[open]");
      checkEl.replaceChildren();
      checkEl.hidden = !c;
      if (!c) return;
      var summary = document.createElement("p"); summary.className = "rule-summary";
      summary.textContent = (c.level === "error" ? "수정 필요 · " : c.level === "warn" ? "살펴보기 · " : "규칙 점검 · ") + c.msg;
      checkEl.appendChild(summary);
      var issues = c.issues || [];
      if (issues.length) {
        var detail = document.createElement("details"), label = document.createElement("summary");
        label.textContent = "문제와 안내 " + issues.length + "개 · 눌러서 위치 찾기";
        detail.appendChild(label); detail.open = wasOpen || c.level === "error";
        var list = document.createElement("ul");
        issues.forEach(function (issue) {
          var row = document.createElement("li"), button = document.createElement("button");
          button.textContent = (issue.level === "error" ? "수정: " : "참고: ") + issue.message;
          button.disabled = !issue.id; button.addEventListener("click", function () { focusIssue(issue); });
          row.appendChild(button); list.appendChild(row);
        });
        detail.appendChild(list); checkEl.appendChild(detail);
      }
    };
    self.live = function (map) {
      var els = canvas.querySelectorAll(".live");
      for (var i = 0; i < els.length; i++) {
        var el = els[i], x = map ? map[+el.parentNode.dataset.id] : undefined;
        if (x === undefined) { el.hidden = true; continue; }
        var a = Math.abs(x);
        el.textContent = (x < 0 ? "−" : "+") + (a >= 10 ? a.toFixed(0) : a.toFixed(1));
        el.className = "live" + (x < 0 ? " neg" : "");
        el.hidden = false;
      }
    };

    defaults();
    buildGuide(1, 1);
    commit();
    try { setZoom(parseFloat(localStorage.getItem("ps.zoom")) || 1); } catch (err) { setZoom(1); }
    render();
    paint();
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () { decorate(canvas); decorate(paletteEl); });
    }
  }

  PS.Blocks = Blocks;
})(window.PS = window.PS || {});
