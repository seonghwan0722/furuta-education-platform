/* RL 블록 실험실 — 블록 에디터 + 학습/시험 주행/내보내기 화면 (외부 라이브러리 없음) */
"use strict";

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "style") e.style.cssText = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
};
const SVGNS = "http://www.w3.org/2000/svg";
const COLORS = ["#2563eb", "#e53935", "#43a047", "#fb8c00", "#8e24aa", "#00897b", "#6d4c41", "#d81b60", "#546e7a"];

const S = {
  schema: null, cats: {}, templates: [],
  graph: { blocks: [], wires: [] },
  sel: null,            // {kind:'block'|'wire', id|index}
  view: { x: 40, y: 30, z: 1 },
  runs: [], compare: new Set(), job: null, polling: null,
  roll: null, playing: true, frame: 0, lastRun: null,
};

// ================================================================ 통신
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  return r.json();
}
function toast(msg, kind = "") {
  const t = el("div", { class: "toast " + kind }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "err" ? 7000 : 3500);
}
function status(msg) { $("#status").textContent = msg; }

// ================================================================ 시작
async function init() {
  const sc = await api("/api/schema");
  S.schema = sc.types;
  for (const [id, name, color] of sc.categories) S.cats[id] = { name, color };
  S.templates = await api("/api/templates");
  buildPalette();
  for (const t of S.templates) $("#tplSelect").append(el("option", { value: t.id }, t.title));
  $("#tplSelect").value = "level1";

  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("blocklab.graph") || "null"); } catch (e) { saved = null; }
  loadGraph(saved && saved.blocks && saved.blocks.length ? saved : S.templates.find((t) => t.id === "level1").graph, false);

  bindToolbar();
  bindCanvas();
  await refreshRuns();
  const st = await api("/api/train/status");
  if (st.status === "running" || st.status === "starting") startPolling();
  renderPi();
  window.addEventListener("resize", () => { drawTrainCharts(); drawRollCharts(); });
}

function blockColor(type) { return S.cats[S.schema[type].category].color; }

// ================================================================ 팔레트
function buildPalette() {
  const pal = $("#palette");
  pal.innerHTML = "";
  for (const [cid, cat] of Object.entries(S.cats)) {
    pal.append(el("h4", {}, cat.name));
    for (const [type, def] of Object.entries(S.schema)) {
      if (def.category !== cid) continue;
      const it = el("div", { class: "pitem", style: `--c:${cat.color}`, title: def.desc },
        el("span", { class: "ic" }, def.icon), def.label);
      it.addEventListener("pointerdown", (ev) => paletteDrag(ev, type));
      pal.append(it);
    }
  }
}

function paletteDrag(ev, type) {
  ev.preventDefault();
  const def = S.schema[type];
  const ghost = el("div", { class: "ghost", style: `--c:${blockColor(type)}` }, `${def.icon} ${def.label}`);
  document.body.append(ghost);
  const move = (e) => { ghost.style.left = e.clientX + 8 + "px"; ghost.style.top = e.clientY + 8 + "px"; };
  move(ev);
  const up = (e) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    ghost.remove();
    const r = $("#canvas").getBoundingClientRect();
    let x, y;
    if (e.clientX > r.left && e.clientX < r.right && e.clientY > r.top && e.clientY < r.bottom) {
      [x, y] = toWorld(e.clientX, e.clientY);
    } else {                       // 그냥 클릭하면 화면 가운데에
      [x, y] = toWorld(r.left + r.width / 2, r.top + r.height / 2);
    }
    addBlock(type, x - 80, y - 15);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function newId() {
  let n = 1;
  const ids = new Set(S.graph.blocks.map((b) => b.id));
  while (ids.has("b" + n)) n++;
  return "b" + n;
}

function addBlock(type, x, y) {
  if (type === "plant" && S.graph.blocks.some((b) => b.type === "plant")) return toast("퓨루타 진자 블록은 하나만 놓을 수 있어요.", "err");
  if (type === "agent" && S.graph.blocks.some((b) => b.type === "agent")) return toast("PPO 에이전트 블록은 하나만 놓을 수 있어요.", "err");
  const params = {};
  for (const p of S.schema[type].params) params[p.key] = structuredClone(p.default);
  const b = { id: newId(), type, x: Math.round(x), y: Math.round(y), params };
  S.graph.blocks.push(b);
  S.sel = { kind: "block", id: b.id };
  renderAll();
}

// ================================================================ 그래프 그리기
function loadGraph(g, fit = true) {
  S.graph = structuredClone(g);
  for (const b of S.graph.blocks) {
    const def = S.schema[b.type];
    if (!def) continue;
    for (const p of def.params) if (!(p.key in (b.params ||= {}))) b.params[p.key] = structuredClone(p.default);
  }
  S.graph.blocks = S.graph.blocks.filter((b) => S.schema[b.type]);
  S.sel = null;
  renderAll();
  if (fit) setTimeout(fitView, 0);
}

function save() { try { localStorage.setItem("blocklab.graph", JSON.stringify(S.graph)); } catch (e) { /* 저장 안 돼도 괜찮음 */ } }

function renderAll() {
  const world = $("#world");
  world.querySelectorAll(".block").forEach((n) => n.remove());
  for (const b of S.graph.blocks) world.append(renderBlock(b));
  applyView();
  renderWires();
  renderProps();
  save();
}

function summary(b) {
  const p = b.params;
  switch (b.type) {
    case "plant": return [el("b", {}, p.model === "cad" ? "CAD 모델" : "막대 모델"), el("br"), `${p.max_torque} N·m`, el("br"), `${p.episode_s}초 · ${p.ctrl_ms}ms`];
    case "agent": return [el("b", {}, "PPO"), el("br"), `${(+p.total_steps).toLocaleString()} 스텝`, el("br"), `lr ${p.learning_rate}`];
    case "randomize": return [`무게 ±${p.mass_pct}%`, el("br"), `힘 ±${p.torque_pct}%`, el("br"), `잡음 ${p.noise_deg}°`];
    case "const": return [el("b", {}, String(p.value))];
    case "gain": return [el("b", {}, "× " + p.k)];
    case "sum": return [el("b", {}, String(p.signs))];
    case "product": return [el("b", {}, "a × b")];
    case "square": return [el("b", {}, "x²")];
    case "abs": return [el("b", {}, "|x|")];
    case "cos": return [el("b", {}, "cos x")];
    case "sin": return [el("b", {}, "sin x")];
    case "compare": return [el("b", {}, `x ${p.op} ${p.threshold}`)];
    case "limit": return [el("b", {}, `${p.lo} ~ ${p.hi}`)];
    case "reward": return [el("b", {}, String(p.name)), el("br"), `× ${p.weight}`];
    case "terminate": return [`벌점 ${p.penalty}`];
    case "scope": return [String(p.title)];
    case "export": return [String(p.name)];
  }
  return [];
}

function renderBlock(b) {
  const def = S.schema[b.type];
  const connectedIn = new Set(S.graph.wires.filter((w) => w.dst[0] === b.id).map((w) => w.dst[1]));
  const connectedOut = new Set(S.graph.wires.filter((w) => w.src[0] === b.id).map((w) => w.src[1]));
  const port = (side, [name, kind, label]) => {
    const conn = side === "in" ? connectedIn.has(name) : connectedOut.has(name);
    const p = el("div", { class: `port ${side} k-${kind}${conn ? " connected" : ""}`, "data-block": b.id, "data-port": name, "data-side": side, "data-kind": kind },
      el("span", { class: "dot" }), el("span", { class: "pl" }, label));
    p.addEventListener("pointerdown", (ev) => wireDrag(ev, b.id, name, side, kind));
    return p;
  };
  const node = el("div", {
    class: "block" + (b.type === "plant" ? " wide" : "") + (S.sel && S.sel.kind === "block" && S.sel.id === b.id ? " sel" : ""),
    style: `--c:${blockColor(b.type)};left:${b.x}px;top:${b.y}px`, "data-id": b.id,
  },
  el("div", { class: "bhead" }, `${def.icon} ${b.label || def.label}`),
  el("div", { class: "bbody" },
    el("div", { class: "bcol" }, def.inputs.map((p) => port("in", p))),
    el("div", { class: "bsum" }, summary(b)),
    el("div", { class: "bcol" }, def.outputs.map((p) => port("out", p)))));
  node.addEventListener("pointerdown", (ev) => blockDrag(ev, b));
  return node;
}

function portPos(bid, pname, side) {
  const n = document.querySelector(`.port[data-block="${bid}"][data-port="${pname}"][data-side="${side}"] .dot`);
  if (!n) return null;
  const r = n.getBoundingClientRect();
  const w = $("#world").getBoundingClientRect();
  return [(r.left + r.width / 2 - w.left) / S.view.z, (r.top + r.height / 2 - w.top) / S.view.z];
}

function curve(a, b) {
  const dx = Math.max(40, Math.abs(b[0] - a[0]) * 0.5);
  if (b[0] < a[0] + 20) {             // 되먹임 선: 아래로 돌아가기
    const lo = Math.max(a[1], b[1]) + 60;
    return `M${a[0]},${a[1]} C${a[0] + 60},${a[1]} ${a[0] + 60},${lo} ${(a[0] + b[0]) / 2},${lo} S${b[0] - 60},${b[1]} ${b[0]},${b[1]}`;
  }
  return `M${a[0]},${a[1]} C${a[0] + dx},${a[1]} ${b[0] - dx},${b[1]} ${b[0]},${b[1]}`;
}

function renderWires() {
  const svg = $("#wires");
  svg.innerHTML = "";
  S.graph.wires.forEach((w, i) => {
    const a = portPos(w.src[0], w.src[1], "out");
    const b = portPos(w.dst[0], w.dst[1], "in");
    if (!a || !b) return;
    const src = S.graph.blocks.find((x) => x.id === w.src[0]);
    const kind = (S.schema[src.type].outputs.find((p) => p[0] === w.src[1]) || [])[1] || "signal";
    const d = curve(a, b);
    const sel = S.sel && S.sel.kind === "wire" && S.sel.index === i;
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", d);
    p.setAttribute("class", `w ${kind}${sel ? " sel" : ""}`);
    const hit = document.createElementNS(SVGNS, "path");
    hit.setAttribute("d", d);
    hit.setAttribute("class", "hit");
    hit.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); S.sel = { kind: "wire", index: i }; renderWires(); renderProps(); });
    svg.append(p, hit);
  });
}

// ================================================================ 끌기: 블록, 선, 화면
function toWorld(cx, cy) {
  const r = $("#canvas").getBoundingClientRect();
  return [(cx - r.left - S.view.x) / S.view.z, (cy - r.top - S.view.y) / S.view.z];
}
function applyView() { $("#world").style.transform = `translate(${S.view.x}px,${S.view.y}px) scale(${S.view.z})`; }

function blockDrag(ev, b) {
  if (ev.target.closest(".port")) return;
  ev.stopPropagation();
  const node = ev.currentTarget;
  const changed = !(S.sel && S.sel.kind === "block" && S.sel.id === b.id);
  S.sel = { kind: "block", id: b.id };
  document.querySelectorAll(".block.sel").forEach((n) => n.classList.remove("sel"));
  node.classList.add("sel");
  if (changed) renderProps();
  const [sx, sy] = [ev.clientX, ev.clientY], [bx, by] = [b.x, b.y];
  const move = (e) => {
    b.x = Math.round(bx + (e.clientX - sx) / S.view.z);
    b.y = Math.round(by + (e.clientY - sy) / S.view.z);
    node.style.left = b.x + "px";
    node.style.top = b.y + "px";
    renderWires();
  };
  const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); save(); };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function wireDrag(ev, bid, pname, side, kind) {
  ev.stopPropagation();
  ev.preventDefault();
  const start = portPos(bid, pname, side);
  const tmp = document.createElementNS(SVGNS, "path");
  tmp.setAttribute("class", "tmp");
  $("#wires").append(tmp);
  const want = side === "out" ? "in" : "out";
  const targets = [...document.querySelectorAll(`.port[data-side="${want}"][data-kind="${kind}"]`)].filter((n) => n.dataset.block !== bid);
  targets.forEach((n) => n.classList.add("drop-ok"));
  const move = (e) => {
    const p = toWorld(e.clientX, e.clientY);
    tmp.setAttribute("d", side === "out" ? curve(start, p) : curve(p, start));
  };
  const up = (e) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    tmp.remove();
    targets.forEach((n) => n.classList.remove("drop-ok"));
    const hit = document.elementFromPoint(e.clientX, e.clientY);
    const tp = hit && hit.closest(".port");
    if (!tp) return;
    if (tp.dataset.side !== want || tp.dataset.block === bid) return;
    if (tp.dataset.kind !== kind) return toast("모양(색)이 같은 포트끼리만 연결할 수 있어요.", "err");
    const src = side === "out" ? [bid, pname] : [tp.dataset.block, tp.dataset.port];
    const dst = side === "out" ? [tp.dataset.block, tp.dataset.port] : [bid, pname];
    // 입력 하나에는 선 하나만
    S.graph.wires = S.graph.wires.filter((w) => !(w.dst[0] === dst[0] && w.dst[1] === dst[1]));
    S.graph.wires.push({ src, dst });
    renderAll();
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function bindCanvas() {
  const cv = $("#canvas");
  cv.addEventListener("pointerdown", (ev) => {
    if (ev.target.closest(".block")) return;
    if (S.sel) { S.sel = null; renderAll(); }
    cv.classList.add("panning");
    const [sx, sy, vx, vy] = [ev.clientX, ev.clientY, S.view.x, S.view.y];
    const move = (e) => { S.view.x = vx + e.clientX - sx; S.view.y = vy + e.clientY - sy; applyView(); };
    const up = () => { cv.classList.remove("panning"); window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  cv.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    zoomAt(ev.clientX, ev.clientY, ev.deltaY < 0 ? 1.1 : 1 / 1.1);
  }, { passive: false });
  document.querySelectorAll("#zoomCtl button").forEach((b) => b.addEventListener("click", () => {
    const r = cv.getBoundingClientRect();
    if (b.dataset.z === "fit") return fitView();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, b.dataset.z === "in" ? 1.2 : 1 / 1.2);
  }));
  window.addEventListener("keydown", (ev) => {
    if (ev.target.matches("input, select, textarea")) return;
    if ((ev.key === "Delete" || ev.key === "Backspace") && S.sel) { ev.preventDefault(); deleteSel(); }
  });
}

function zoomAt(cx, cy, k) {
  const r = $("#canvas").getBoundingClientRect();
  const z = Math.min(2, Math.max(0.3, S.view.z * k));
  const [wx, wy] = toWorld(cx, cy);
  S.view.z = z;
  S.view.x = cx - r.left - wx * z;
  S.view.y = cy - r.top - wy * z;
  applyView();
}

function fitView() {
  const nodes = [...document.querySelectorAll(".block")];
  if (!nodes.length) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const b of S.graph.blocks) {
    const n = document.querySelector(`.block[data-id="${b.id}"]`);
    x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y);
    x1 = Math.max(x1, b.x + n.offsetWidth); y1 = Math.max(y1, b.y + n.offsetHeight + 40);
  }
  const r = $("#canvas").getBoundingClientRect();
  const z = Math.min(1.2, Math.max(0.3, Math.min((r.width - 60) / (x1 - x0), (r.height - 60) / (y1 - y0))));
  S.view = { z, x: (r.width - (x1 - x0) * z) / 2 - x0 * z, y: 30 - y0 * z + Math.max(0, (r.height - 60 - (y1 - y0) * z) / 2) };
  applyView();
}

function deleteSel() {
  if (!S.sel) return;
  if (S.sel.kind === "wire") S.graph.wires.splice(S.sel.index, 1);
  else {
    S.graph.blocks = S.graph.blocks.filter((b) => b.id !== S.sel.id);
    S.graph.wires = S.graph.wires.filter((w) => w.src[0] !== S.sel.id && w.dst[0] !== S.sel.id);
  }
  S.sel = null;
  renderAll();
}

// ================================================================ 속성 창
let showAdv = false;
function renderProps() {
  const box = $("#props");
  box.innerHTML = "";
  if (S.sel && S.sel.kind === "wire") {
    box.append(el("h3", {}, "선"), el("div", { class: "desc" }, "선택한 선을 지우려면 Delete 키나 아래 버튼을 누르세요."),
      el("button", { class: "danger", onclick: deleteSel }, "선 지우기"));
    return;
  }
  const b = S.sel && S.graph.blocks.find((x) => x.id === S.sel.id);
  if (!b) return renderHelp(box);
  const def = S.schema[b.type];
  box.append(el("h3", {}, `${def.icon} ${def.label}`), el("div", { class: "desc" }, def.desc));
  const lab = el("input", { type: "text", value: b.label || "", placeholder: def.label });
  lab.addEventListener("change", () => { b.label = lab.value.trim() || undefined; renderAll(); });
  box.append(el("div", { class: "field" }, el("label", {}, "블록 이름"), lab));
  const hasAdv = def.params.some((p) => p.adv);
  for (const p of def.params) {
    if (p.adv && !showAdv) continue;
    let inp;
    if (p.type === "select") {
      inp = el("select", {}, p.options.map(([v, t]) => el("option", { value: v }, t)));
      inp.value = b.params[p.key];
    } else {
      inp = el("input", { type: p.type === "number" ? "number" : "text", value: b.params[p.key], step: p.step ?? "any", min: p.min, max: p.max });
    }
    inp.addEventListener("change", () => {
      let v = inp.value;
      if (p.type === "number") {
        v = parseFloat(v);
        if (!Number.isFinite(v)) { toast(`${p.label}에는 숫자를 넣어 주세요.`, "err"); inp.value = b.params[p.key]; return; }
      }
      b.params[p.key] = v;
      const node = document.querySelector(`.block[data-id="${b.id}"]`);
      node.replaceWith(renderBlock(b));
      renderWires();
      save();
    });
    box.append(el("div", { class: "field" }, el("label", {}, p.label), inp, p.help ? el("div", { class: "help" }, p.help) : null));
  }
  if (hasAdv) box.append(el("span", { class: "advtoggle", onclick: () => { showAdv = !showAdv; renderProps(); } }, showAdv ? "▲ 고급 설정 숨기기" : "▼ 고급 설정 보기"));
  box.append(el("div", {}, el("button", { class: "danger", onclick: deleteSel }, "블록 지우기")));
}

async function renderHelp(box) {
  box.append(el("h3", {}, "사용 방법"),
    el("div", { class: "card" }, el("h4", {}, "① 블록 놓고 잇기"), el("ul", {},
      el("li", {}, "왼쪽 목록에서 블록을 끌어다 놓아요."),
      el("li", {}, "오른쪽 포트(●)를 끌어서 다른 블록의 왼쪽 포트에 놓으면 선이 이어져요. 같은 색끼리만 이어져요."),
      el("li", {}, "블록을 누르면 여기서 값을 바꿀 수 있어요. 지우기는 Delete 키."))),
    el("div", { class: "card" }, el("h4", {}, "② 보상 설계 → 학습"), el("ul", {},
      el("li", {}, "진자 센서값을 계산 블록으로 가공해서 '보상 항'에 연결해요. 보상 항들의 합이 점수예요."),
      el("li", {}, "▶ 학습 시작을 누르면 PPO가 점수를 높이는 방법을 스스로 찾아요."))),
    el("div", { class: "card" }, el("h4", {}, "③ 확인 → 라즈베리파이"), el("ul", {},
      el("li", {}, "🧪 시험 주행으로 학습된 정책을 움직여 보고, 스코프로 신호를 확인해요."),
      el("li", {}, "'똑바로 선 시간 비율'로 서로 다른 보상 설계를 공정하게 비교할 수 있어요."),
      el("li", {}, "🍓 탭에서 정책을 라즈베리파이용 파일로 내보내요."))));
  const chk = el("div", { class: "card" }, el("h4", {}, "지금 블록 상태"), el("div", { class: "muted" }, "검사 중…"));
  box.append(chk);
  const r = await api("/api/check", { graph: S.graph });
  const body = chk.lastChild;
  body.innerHTML = "";
  if (!r.ok) { body.append(el("div", { class: "err" }, "⚠ " + r.error)); return; }
  if (r.trainable) body.append(el("div", { class: "ok" }, `✅ 학습할 수 있어요. 보상 항: ${r.rewards.join(", ")}`));
  for (const w of r.warnings) body.append(el("div", { class: r.trainable ? "warn" : "err" }, "⚠ " + w));
}

// ================================================================ 툴바
function bindToolbar() {
  $("#btnLoadTpl").onclick = () => {
    const t = S.templates.find((x) => x.id === $("#tplSelect").value);
    if (S.graph.blocks.length && !confirm(`'${t.title}' 예제를 불러올까요? 지금 화면의 블록은 사라져요.`)) return;
    loadGraph(t.graph);
    status(t.desc);
  };
  $("#btnNew").onclick = () => { if (confirm("모든 블록을 지울까요?")) loadGraph({ blocks: [], wires: [] }); };
  $("#btnSave").onclick = () => {
    const blob = new Blob([JSON.stringify(S.graph, null, 1)], { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: ($("#runName").value.trim() || "blocklab") + ".json" });
    a.click();
  };
  $("#btnOpen").onclick = () => $("#fileOpen").click();
  $("#fileOpen").onchange = async () => {
    const f = $("#fileOpen").files[0];
    if (!f) return;
    try { loadGraph(JSON.parse(await f.text())); toast("불러왔어요.", "ok"); } catch (e) { toast("파일을 읽을 수 없어요.", "err"); }
    $("#fileOpen").value = "";
  };
  $("#btnTrain").onclick = startTraining;
  $("#btnStop").onclick = async () => { await api("/api/train/stop", {}); status("멈추는 중… 지금까지 배운 정책을 저장해요."); };
  $("#btnRollout").onclick = runRollout;
  $("#btnView").onclick = async () => {
    const r = await api("/api/view", { graph: S.graph, run_id: $("#policySel").value || null });
    if (!r.ok) toast(r.error, "err"); else toast("3D 뷰어 창을 띄웠어요 (서버를 실행한 컴퓨터 화면).", "ok");
  };
  $("#btnToggleRes").onclick = () => {
    document.body.classList.toggle("res-collapsed");
    $("#btnToggleRes").textContent = document.body.classList.contains("res-collapsed") ? "펼치기" : "접기";
    setTimeout(() => { drawTrainCharts(); drawRollCharts(); }, 50);
  };
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#btnPlay").onclick = () => { S.playing = !S.playing; $("#btnPlay").textContent = S.playing ? "⏸" : "▶"; };
  $("#tSlider").oninput = () => { S.frame = +$("#tSlider").value; S.playing = false; $("#btnPlay").textContent = "▶"; drawFrame(); };
}

function showTab(id) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === id));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("on", p.id === "tab-" + id));
  if (document.body.classList.contains("res-collapsed")) $("#btnToggleRes").click();
  setTimeout(() => { if (id === "train") drawTrainCharts(); if (id === "roll") drawRollCharts(); }, 0);
}

// ================================================================ 학습
async function startTraining() {
  const r = await api("/api/train", { graph: S.graph, name: $("#runName").value });
  if (!r.ok) return toast(r.error, "err");
  for (const w of r.warnings || []) toast("⚠ " + w);
  toast("학습을 시작했어요!", "ok");
  S.compare.add(r.id);
  showTab("train");
  startPolling();
}

function startPolling() {
  if (S.polling) return;
  $("#btnTrain").hidden = true;
  $("#btnStop").hidden = false;
  $("#trainBar").hidden = false;
  S.polling = setInterval(poll, 1000);
  poll();
}

const fmtTime = (s) => (s == null ? "?" : s >= 60 ? `${Math.floor(s / 60)}분 ${Math.round(s % 60)}초` : `${Math.round(s)}초`);

async function poll() {
  const st = await api("/api/train/status");
  S.job = st;
  if (st.status === "idle") return stopPolling();
  const pct = st.total ? (100 * st.timesteps) / st.total : 0;
  const last = st.curve.length ? st.curve[st.curve.length - 1] : null;
  $("#tbFill").style.width = pct.toFixed(1) + "%";
  $("#tbTitle").textContent = `학습 중: ${st.name}`;
  $("#tbInfo").textContent = `${st.timesteps.toLocaleString()} / ${st.total.toLocaleString()} 스텝 · ${fmtTime(st.elapsed)} 지남 · 남은 시간 약 ${fmtTime(st.eta)}`
    + (last ? ` · 점수 ${last.ret.toFixed(1)} · 선 시간 ${(100 * last.upright).toFixed(0)}%` : "");
  status($("#tbTitle").textContent + " — " + $("#tbInfo").textContent);
  drawTrainCharts();
  if (st.status !== "running" && st.status !== "starting") {
    stopPolling();
    if (st.status === "error") toast("학습 오류: " + st.error, "err");
    else toast(st.status === "done" ? "학습 끝! 🧪 시험 주행으로 확인해 보세요." : "학습을 멈췄어요. 지금까지 배운 정책을 저장했어요.", "ok");
    status(`학습 ${st.status === "done" ? "완료" : st.status === "stopped" ? "멈춤" : "오류"}: ${st.name}`);
    S.lastRun = st.id;
    await refreshRuns();
    $("#policySel").value = st.id;
    if (st.status !== "error") runRollout();
  }
}

function stopPolling() {
  clearInterval(S.polling);
  S.polling = null;
  $("#btnTrain").hidden = false;
  $("#btnStop").hidden = true;
  $("#trainBar").hidden = true;
}

async function refreshRuns() {
  S.runs = await api("/api/runs");
  const sel = $("#policySel");
  const cur = sel.value;
  sel.innerHTML = "";
  sel.append(el("option", { value: "" }, "정책 없음 (모터 0)"));
  for (const r of S.runs) if (r.has_model) sel.append(el("option", { value: r.id }, `정책: ${r.name}`));
  sel.value = [...sel.options].some((o) => o.value === cur) ? cur : (S.runs.find((r) => r.has_model) || {}).id || "";
  if (!S.compare.size && S.runs.length) S.compare.add(S.runs[0].id);
  renderRunTable();
  drawTrainCharts();
  renderPi();
}

function runColor(id) {
  const ids = S.runs.map((r) => r.id).reverse();
  const i = ids.indexOf(id);
  return COLORS[(i < 0 ? ids.length : i) % COLORS.length];
}

function renderRunTable() {
  const t = $("#runTable");
  t.innerHTML = "";
  t.append(el("tr", {}, ["비교", "실험 이름", "상태", "학습 스텝", "걸린 시간", "마지막 점수", "선 시간", ""].map((h) => el("th", {}, h))));
  if (!S.runs.length) t.append(el("tr", {}, el("td", { colspan: 8, class: "muted" }, "아직 학습 기록이 없어요.")));
  const stName = { done: "완료", stopped: "멈춤", error: "오류", running: "학습 중", starting: "준비 중" };
  for (const r of S.runs) {
    const cb = el("input", { type: "checkbox" });
    cb.checked = S.compare.has(r.id);
    cb.onchange = () => { cb.checked ? S.compare.add(r.id) : S.compare.delete(r.id); drawTrainCharts(); };
    t.append(el("tr", {},
      el("td", {}, cb, " ", el("span", { class: "sw", style: `background:${runColor(r.id)}` })),
      el("td", {}, r.name), el("td", { class: r.status === "error" ? "err" : "" }, stName[r.status] || r.status),
      el("td", {}, (r.timesteps || 0).toLocaleString()), el("td", {}, fmtTime(r.seconds)),
      el("td", {}, r.final_return == null ? "-" : r.final_return.toFixed(1)),
      el("td", {}, r.final_upright == null ? "-" : (100 * r.final_upright).toFixed(0) + "%"),
      el("td", {},
        el("button", { class: "small", disabled: !r.has_model, onclick: () => { $("#policySel").value = r.id; runRollout(); } }, "🧪 시험 주행"), " ",
        el("button", { class: "small", onclick: () => loadRunGraph(r) }, "블록 불러오기"), " ",
        el("button", { class: "small", disabled: !r.has_model, onclick: () => doExport(r.id) }, "🍓 내보내기"))));
  }
}

async function loadRunGraph(r) {
  if (!confirm(`'${r.name}' 실험에 썼던 블록을 불러올까요? 지금 화면의 블록은 사라져요.`)) return;
  const g = await api(`/api/run/${r.id}/graph`);
  if (g.ok === false) return toast(g.error, "err");
  loadGraph(g);
}

// ================================================================ 차트 (간단한 선 그래프)
function drawChart(cv, series, opt = {}) {
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (!W || !H) return;
  cv.width = W * dpr; cv.height = H * dpr;
  const c = cv.getContext("2d");
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, W, H);
  const L = 46, R = 8, T = 8, B = 22 + (opt.legend ? 0 : 0);
  let xs = [], ys = [];
  for (const s of series) { xs = xs.concat(s.x); ys = ys.concat(s.y); }
  c.font = "11px sans-serif";
  c.fillStyle = "#9ca3af";
  if (!xs.length) { c.fillText(opt.empty || "아직 데이터가 없어요", L, H / 2); return; }
  let x0 = opt.x0 ?? Math.min(...xs), x1 = opt.x1 ?? Math.max(...xs);
  let y0 = opt.y0 ?? Math.min(...ys), y1 = opt.y1 ?? Math.max(...ys);
  if (x1 === x0) x1 = x0 + 1;
  if (y1 === y0) { y0 -= 1; y1 += 1; }
  const pad = (y1 - y0) * 0.06; if (opt.y0 === undefined) y0 -= pad; if (opt.y1 === undefined) y1 += pad;
  const X = (v) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
  const Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  c.strokeStyle = "#e5e7eb"; c.lineWidth = 1;
  c.fillStyle = "#6b7280";
  for (let i = 0; i <= 4; i++) {
    const v = y0 + ((y1 - y0) * i) / 4, y = Y(v);
    c.beginPath(); c.moveTo(L, y); c.lineTo(W - R, y); c.stroke();
    c.fillText(fmtNum(v), 2, y + 4);
  }
  for (let i = 0; i <= 4; i++) {
    const v = x0 + ((x1 - x0) * i) / 4;
    c.fillText(opt.xfmt ? opt.xfmt(v) : fmtNum(v), X(v) - (i === 4 ? 30 : i ? 12 : 0), H - 6);
  }
  if (y0 < 0 && y1 > 0) { c.strokeStyle = "#9ca3af"; c.beginPath(); c.moveTo(L, Y(0)); c.lineTo(W - R, Y(0)); c.stroke(); }
  for (const s of series) {
    c.strokeStyle = s.color; c.lineWidth = s.width || 2;
    c.beginPath();
    s.x.forEach((xv, i) => (i ? c.lineTo(X(xv), Y(s.y[i])) : c.moveTo(X(xv), Y(s.y[i]))));
    c.stroke();
  }
  if (opt.cursor != null) { c.strokeStyle = "#111827"; c.lineWidth = 1; c.beginPath(); c.moveTo(X(opt.cursor), T); c.lineTo(X(opt.cursor), H - B); c.stroke(); }
  // 범례
  let lx = L + 6;
  c.font = "11px sans-serif";
  for (const s of series) {
    if (!s.name) continue;
    const w = c.measureText(s.name).width;
    if (lx + w + 20 > W) break;
    c.fillStyle = s.color; c.fillRect(lx, T + 2, 10, 3);
    c.fillStyle = "#374151"; c.fillText(s.name, lx + 13, T + 8);
    lx += w + 24;
  }
}
const fmtNum = (v) => (Math.abs(v) >= 10000 ? (v / 1000).toFixed(0) + "k" : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(1) : v.toFixed(2));

function drawTrainCharts() {
  if (!$("#tab-train").classList.contains("on")) return;
  const curves = [];
  for (const r of S.runs) if (S.compare.has(r.id)) curves.push({ id: r.id, name: r.name, curve: r.curve || [] });
  const job = S.job;
  if (job && (job.status === "running" || job.status === "starting")) {
    const ex = curves.find((c) => c.id === job.id);
    if (ex) ex.curve = job.curve; else curves.push({ id: job.id, name: job.name, curve: job.curve });
  }
  const xf = (v) => (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v.toFixed(0));
  drawChart($("#chRet"), curves.map((c) => ({ name: c.name, color: runColor(c.id), x: c.curve.map((p) => p.t), y: c.curve.map((p) => p.ret) })),
    { xfmt: xf, empty: "학습을 시작하면 그래프가 그려져요" });
  drawChart($("#chUp"), curves.map((c) => ({ name: c.name, color: runColor(c.id), x: c.curve.map((p) => p.t), y: c.curve.map((p) => 100 * p.upright) })),
    { xfmt: xf, y0: 0, y1: 100 });
  // 보상 항: 지금 학습 중이면 그것, 아니면 가장 최근에 비교 선택된 실험
  const focus = (job && job.status === "running") ? job : curves[curves.length - 1];
  const cv = focus ? focus.curve || [] : [];
  const keys = [...new Set(cv.flatMap((p) => Object.keys(p.terms || {})))];
  drawChart($("#chTerms"), keys.map((k, i) => ({ name: k, color: COLORS[i % COLORS.length], x: cv.map((p) => p.t), y: cv.map((p) => (p.terms[k] ?? 0)) })), { xfmt: xf });
}

// ================================================================ 시험 주행
async function runRollout() {
  const run_id = $("#policySel").value || null;
  status("시험 주행 계산 중…");
  const r = await api("/api/rollout", { graph: S.graph, run_id, seconds: +$("#duration").value || 8 });
  if (!r.ok) { status(""); return toast(r.error, "err"); }
  S.roll = r;
  S.frame = 0;
  S.playing = true;
  $("#btnPlay").textContent = "⏸";
  $("#tSlider").max = r.t.length - 1;
  const name = run_id ? (S.runs.find((x) => x.id === run_id) || {}).name : "정책 없음 (모터 0)";
  $("#rollInfo").innerHTML = "";
  $("#rollInfo").append(
    el("div", {}, el("b", {}, "정책: "), name),
    el("div", {}, el("b", {}, "점수 합계: "), r.return[r.return.length - 1].toFixed(1), "  ·  ", el("b", {}, "선 시간: "), (100 * r.upright).toFixed(0) + "%"),
    r.terminated ? el("div", { class: "warn" }, `판 끝내기 조건이 ${r.t[r.t.length - 1].toFixed(2)}초에 걸렸어요.`) : null,
    el("div", { class: "muted" }, "지금 화면의 진자 설정(무게·토크…)으로 돌려요. 진자를 바꿔서 정책이 얼마나 버티는지 시험해 보세요."));
  showTab("roll");
  status(`시험 주행: ${name} · 점수 ${r.return[r.return.length - 1].toFixed(1)} · 선 시간 ${(100 * r.upright).toFixed(0)}%`);
  drawRollCharts();
}

function drawRollCharts() {
  const box = $("#rollCharts");
  const r = S.roll;
  if (!r || !$("#tab-roll").classList.contains("on")) return;
  const items = [{ title: "보상 누적 (항별)", series: Object.entries(r.parts).map(([k, v], i) => ({ name: k, color: COLORS[i % COLORS.length], x: r.t, y: v })) }];
  for (const sc of r.scopes) items.push({ title: "📈 " + sc.title, series: sc.chans.map((ch, i) => ({ name: ch.label, color: COLORS[i % COLORS.length], x: r.t, y: ch.data })) });
  if (box.children.length !== items.length) {
    box.innerHTML = "";
    for (const it of items) box.append(el("div", { class: "chartbox" }, el("div", { class: "ct" }, it.title), el("canvas")));
  }
  [...box.children].forEach((n, i) => { n.firstChild.textContent = items[i].title; drawChart(n.lastChild, items[i].series, { cursor: r.t[S.frame] }); });
}

function drawFrame() {
  const r = S.roll;
  const cv = $("#animCv");
  const c = cv.getContext("2d");
  c.clearRect(0, 0, cv.width, cv.height);
  if (!r) { c.fillStyle = "#9ca3af"; c.font = "13px sans-serif"; c.fillText("🧪 시험 주행을 누르면 진자가 움직여요", 60, 130); return; }
  const k = Math.min(S.frame, r.t.length - 1);
  const phi = r.phi[k], th = r.theta[k];
  // 3D 점 → 화면 (비스듬히 내려다보기)
  const LA = 1.0, LP = 1.25, yaw = -0.6, pitch = 0.42, sc = 55, cx = 140, cy = 95;
  const P = ([x, y, z]) => {
    const xr = x * Math.cos(yaw) - y * Math.sin(yaw), yr = x * Math.sin(yaw) + y * Math.cos(yaw);
    return [cx + sc * xr, cy - sc * (z * Math.cos(pitch) - yr * Math.sin(pitch))];
  };
  const tip = [LA * Math.cos(phi), LA * Math.sin(phi), 0];
  const t = [-Math.sin(phi), Math.cos(phi), 0];
  const end = [tip[0] + LP * Math.sin(th) * t[0], tip[1] + LP * Math.sin(th) * t[1], -LP * Math.cos(th)];
  const line = (a, b, col, w) => { const A = P(a), B = P(b); c.strokeStyle = col; c.lineWidth = w; c.lineCap = "round"; c.beginPath(); c.moveTo(...A); c.lineTo(...B); c.stroke(); };
  // 바닥 원, 기둥
  c.strokeStyle = "#cbd5e1"; c.lineWidth = 1; c.beginPath();
  for (let i = 0; i <= 40; i++) { const a = (i / 40) * 2 * Math.PI; const p = P([1.1 * Math.cos(a), 1.1 * Math.sin(a), -1.3]); i ? c.lineTo(...p) : c.moveTo(...p); }
  c.stroke();
  line([0, 0, -1.3], [0, 0, 0], "#475569", 10);
  const behind = Math.sin(phi + yaw) > 0;
  const drawPend = () => { line(tip, end, "#e53935", 6); const E = P(end); c.fillStyle = "#b71c1c"; c.beginPath(); c.arc(E[0], E[1], 7, 0, 2 * Math.PI); c.fill(); };
  if (behind) drawPend();
  line([0, 0, 0], tip, "#1e88e5", 8);
  if (!behind) drawPend();
  // 옆에서 본 진자 각도 (θ) 시계
  const gx = 305, gy = 55, gr = 30;
  c.strokeStyle = "#cbd5e1"; c.lineWidth = 2; c.beginPath(); c.arc(gx, gy, gr, 0, 2 * Math.PI); c.stroke();
  c.fillStyle = "#16a34a"; c.beginPath(); c.moveTo(gx, gy); c.arc(gx, gy, gr, -Math.PI / 2 - 0.35, -Math.PI / 2 + 0.35); c.closePath(); c.globalAlpha = 0.25; c.fill(); c.globalAlpha = 1;
  c.strokeStyle = "#e53935"; c.lineWidth = 4; c.beginPath(); c.moveTo(gx, gy); c.lineTo(gx + gr * Math.sin(th), gy + gr * Math.cos(th)); c.stroke();
  c.fillStyle = "#374151"; c.font = "11px sans-serif";
  c.fillText("진자 θ (옆에서)", gx - 38, gy + gr + 16);
  const deg = ((((th * 180) / Math.PI + 180) % 360) + 360) % 360 - 180;
  c.fillText(`θ ${deg.toFixed(0)}°`, gx - 18, gy + gr + 30);
  c.fillText(`φ ${((phi * 180) / Math.PI).toFixed(0)}°`, gx - 18, gy + gr + 44);
  c.font = "bold 13px sans-serif"; c.fillStyle = "#111827";
  c.fillText(`t = ${r.t[k].toFixed(2)} s`, 10, 20);
  c.fillText(`점수 ${r.return[k].toFixed(1)}`, 10, 38);
  $("#tSlider").value = k;
  $("#tLabel").textContent = r.t[k].toFixed(2) + " s";
}

let lastTick = 0, lastChart = 0;
function tick(ts) {
  if (S.roll && S.playing) {
    const n = Math.max(1, Math.round((ts - lastTick) / 1000 / S.roll.dt));
    if (ts - lastTick > 15) {
      S.frame = S.frame + Math.min(n, 10);
      if (S.frame >= S.roll.t.length) S.frame = 0;
      lastTick = ts;
      drawFrame();
      if (ts - lastChart > 120) { lastChart = ts; drawRollCharts(); }
    }
  } else lastTick = ts;
  requestAnimationFrame(tick);
}

// ================================================================ 라즈베리파이
async function doExport(runId) {
  status("라즈베리파이용 파일 만드는 중…");
  const r = await api("/api/export", { run_id: runId });
  if (!r.ok) return toast(r.error, "err");
  S.exported = { runId, ...r };
  renderPi();
  showTab("pi");
  toast("내보내기 완료! zip 파일을 받으세요.", "ok");
  status("라즈베리파이 내보내기 완료");
}

function renderPi() {
  const box = $("#piPane");
  box.innerHTML = "";
  const runs = S.runs.filter((r) => r.has_model);
  const sel = el("select", {}, runs.map((r) => el("option", { value: r.id }, r.name)));
  if (S.exported) sel.value = S.exported.runId;
  box.append(el("h3", { style: "margin:4px 0" }, "🍓 학습된 정책을 라즈베리파이로 옮기기"),
    runs.length ? el("div", {}, "정책 고르기: ", sel, " ", el("button", { class: "primary", onclick: () => doExport(sel.value) }, "내보내기 (zip 만들기)"))
      : el("div", { class: "muted" }, "먼저 학습을 한 번 해 주세요."));
  const e = S.exported;
  if (e) {
    const name = (S.runs.find((r) => r.id === e.runId) || {}).name;
    box.append(el("div", { class: "card", style: "margin-top:10px" },
      el("div", {}, el("b", {}, `${name}`), ` → 신경망 ${[e.layers[0][1], ...e.layers.map((l) => l[0])].join(" → ")}, 제어 주기 ${e.ctrl_ms} ms, 최대 토크 ${e.max_torque} N·m`),
      el("div", { class: e.max_diff < 1e-4 ? "ok" : "err" }, `numpy 계산과 PyTorch 정책의 차이: ${e.max_diff.toExponential(1)} ${e.max_diff < 1e-4 ? "✅ 같아요" : "❌ 확인 필요"}`),
      el("div", { style: "margin-top:6px" }, el("a", { href: `/api/download/${e.runId}/${e.zip}`, download: e.zip }, el("button", { class: "primary" }, `⬇ ${e.zip} 받기`)))));
  }
  box.append(el("div", { class: "card", style: "margin-top:10px" },
    el("h4", {}, "라즈베리파이에서 할 일"),
    el("ol", {},
      el("li", {}, "zip을 라즈베리파이로 복사해서 풀어요 (USB 또는 scp)."),
      el("li", {}, "numpy만 있으면 돼요: ", el("code", {}, "sudo apt install python3-numpy")),
      el("li", {}, "확인: ", el("code", {}, "python3 pi_policy.py --test"), "  → 시뮬레이션과 같은 답이 나오면 '통과'"),
      el("li", {}, "속도: ", el("code", {}, "python3 pi_policy.py --bench"), "  → 제어 주기보다 훨씬 짧아야 해요"),
      el("li", {}, "실제 제어: ", el("code", {}, "python3 pi_policy.py --run --port /dev/ttyACM0"),
        "  (모터 드라이버와 주고받는 부분 SerialMotorBridge 는 우리 기계에 맞게 고쳐 쓰세요)")),
    el("div", { class: "muted" }, "주의: 진자 각도는 '아래로 매달림 = 0', 모터 +방향은 시뮬레이션과 같아야 해요. 처음엔 손으로 진자를 돌려 보며 각도 부호를 꼭 확인하세요.")));
}

init().then(() => { drawFrame(); requestAnimationFrame(tick); });
