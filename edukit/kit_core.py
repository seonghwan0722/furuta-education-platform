"""
kit_core.py — 블록 다이어그램 → MuJoCo 모델 + 제어 신호 계산
==============================================================
에디터에서 만든 그래프(JSON)를 받아서
  1. 기구 블록(바닥·강체·조인트·모터)을 MuJoCo XML(MJCF)로 바꾸고
  2. 신호 블록(상수·게인·PID·스위치 …)을 매 제어 주기마다 계산해서 모터 명령을 만든다.

그래프 JSON 형식:
  {"blocks": [{"id": "b1", "type": "body", "label": "진자", "x": 100, "y": 50, "params": {...}}, ...],
   "wires":  [{"src": ["b1", "frame"], "dst": ["b2", "parent"]}, ...]}

단위 변환: 화면(cm, g, 도) → MuJoCo(m, kg, 도: compiler angle="degree")
"""
import functools
import math
import os
import xml.etree.ElementTree as ET

import numpy as np
import mujoco

from blocks import BLOCK_TYPES, default_params, port_kind

KIT_DIR    = os.path.dirname(os.path.abspath(__file__))
MESH_DIRS  = [os.path.join(KIT_DIR, "meshes"),
              os.path.normpath(os.path.join(KIT_DIR, "..", "models", "legacy_cad", "meshes"))]
PHYS_DT    = 0.002          # 물리 계산 간격 (초)
CTRL_EVERY = 5              # 제어 주기 = 5 × 0.002 = 0.01초 (env.py 와 동일)
CTRL_DT    = PHYS_DT * CTRL_EVERY
MAX_DURATION = 60.0

AXIS_VEC = {"x": "1 0 0", "y": "0 1 0", "z": "0 0 1", "-x": "-1 0 0", "-y": "0 -1 0", "-z": "0 0 -1"}
MESH_SCALE = {"mm": 0.001, "cm": 0.01, "m": 1.0}


class KitError(Exception):
    """아이들에게 그대로 보여줄 수 있는 오류 메시지"""


# ============================================================ 3D 파일(STL) 목록
def list_meshes():
    """사용할 수 있는 STL 파일 이름 → 경로 (edukit/meshes 가 models/legacy_cad/meshes 보다 우선)"""
    found = {}
    for d in MESH_DIRS:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(".stl") and f not in found:
                    found[f] = os.path.join(d, f)
    return found


@functools.lru_cache(maxsize=None)
def _mesh_inertia_mode(path):
    """
    무게중심/관성을 실제 모양("exact")으로 계산할 수 있으면 exact, 아니면 볼록껍질("convex").
    ㄱ자 파이프처럼 오목한 부품은 볼록껍질로 계산하면 무게중심이 크게 틀어진다.
    면 방향이 뒤섞인 STL은 exact 계산이 안 되므로 convex 로 대신한다.
    """
    xml = (f'<mujoco><asset><mesh name="m" file="{path}" inertia="exact"/></asset>'
           f'<worldbody><body><freejoint/><geom type="mesh" mesh="m" mass="1"/></body></worldbody></mujoco>')
    try:
        mujoco.MjModel.from_xml_string(xml)
        return "exact"
    except ValueError:
        return "convex"


# ============================================================ 그래프 정리
class Graph:
    def __init__(self, raw):
        self.blocks = {}
        for b in raw.get("blocks", []):
            if b.get("type") not in BLOCK_TYPES:
                raise KitError(f"모르는 블록 종류예요: {b.get('type')}")
            params = default_params(b["type"])
            params.update(b.get("params") or {})
            self.blocks[b["id"]] = {"id": b["id"], "type": b["type"],
                                    "label": b.get("label") or BLOCK_TYPES[b["type"]]["label"],
                                    "params": params}
        # 입력 포트 하나에는 선 하나만 (마지막 선이 이김)
        self.src_of = {}            # (dst_id, dst_port) -> (src_id, src_port)
        self.dsts_of = {}           # (src_id, src_port) -> [(dst_id, dst_port), ...]
        for w in raw.get("wires", []):
            (s, sp), (d, dp) = w["src"], w["dst"]
            if s not in self.blocks or d not in self.blocks:
                continue
            sk = port_kind(self.blocks[s]["type"], sp, "outputs")
            dk = port_kind(self.blocks[d]["type"], dp, "inputs")
            if sk is None or dk is None or sk != dk:
                continue
            self.src_of[(d, dp)] = (s, sp)
        for (d, dp), (s, sp) in self.src_of.items():
            self.dsts_of.setdefault((s, sp), []).append((d, dp))

    def of_type(self, t):
        return [b for b in self.blocks.values() if b["type"] == t]

    def name(self, bid):
        return f"'{self.blocks[bid]['label']}'"


def _num(v, what, g, bid):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise KitError(f"{g.name(bid)}의 {what} 값이 숫자가 아니에요.")
    if not math.isfinite(x):
        raise KitError(f"{g.name(bid)}의 {what} 값이 이상해요.")
    return x


def _vec(v, what, g, bid, scale=1.0):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise KitError(f"{g.name(bid)}의 {what}에는 숫자 3개가 필요해요.")
    return [_num(x, what, g, bid) * scale for x in v]


def _fmt(vals):
    return " ".join(f"{x:.6g}" for x in vals)


def _rgba(hexcolor):
    h = (hexcolor or "#999999").lstrip("#")
    try:
        r, gg, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        r, gg, b = 0.6, 0.6, 0.6
    return f"{r:.3f} {gg:.3f} {b:.3f} 1"


# ============================================================ 기구 → MJCF
def build_mjcf(g):
    """그래프의 기구 블록으로 MJCF XML 문자열을 만든다. (xml, joint_ids, motor_ids, warnings)"""
    warnings = []
    grounds = g.of_type("ground")
    if not grounds:
        raise KitError("'바닥' 블록이 필요해요. 왼쪽 목록의 [기구]에서 바닥을 추가해 주세요.")
    if len(grounds) > 1:
        raise KitError("'바닥' 블록은 하나만 있어야 해요.")
    ground = grounds[0]

    root = ET.Element("mujoco", model="edukit")
    ET.SubElement(root, "compiler", angle="degree", inertiafromgeom="true", autolimits="true")
    opt = ET.SubElement(root, "option", timestep=str(PHYS_DT), integrator="RK4", gravity="0 0 -9.81")
    ET.SubElement(opt, "flag", contact="disable")          # 부품끼리 부딪히는 계산은 끔
    vis = ET.SubElement(root, "visual")
    ET.SubElement(vis, "global", offwidth="1280", offheight="720")
    asset = ET.SubElement(root, "asset")
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", directional="true", pos="0 0 3", dir="0 0 -1", diffuse="0.8 0.8 0.8")
    ET.SubElement(world, "light", pos="1 -1 1.5", dir="-1 1 -1", diffuse="0.3 0.3 0.3")
    ET.SubElement(world, "geom", name="floor", type="plane", size="1.5 1.5 0.05",
                  rgba=_rgba(ground["params"].get("color")))

    meshes = list_meshes()
    joint_ids, visited = [], set()

    def add_body(body_id, xml_parent, via_joint):
        if body_id in visited:
            raise KitError(f"{g.name(body_id)} 강체가 두 군데에 붙어 있어요.")
        visited.add(body_id)
        b = g.blocks[body_id]
        p = b["params"]
        attrs = {"name": body_id}
        if via_joint is not None:
            jp = g.blocks[via_joint]["params"]
            attrs["pos"] = _fmt(_vec(jp["pos"], "위치", g, via_joint, 0.01))
            attrs["euler"] = _fmt(_vec(jp["rot"], "방향", g, via_joint))
        el = ET.SubElement(xml_parent, "body", **attrs)

        # 조인트 (고정이면 조인트 없이 붙임)
        if via_joint is not None and g.blocks[via_joint]["params"]["jtype"] != "fixed":
            jp = g.blocks[via_joint]["params"]
            if jp["axis"] not in AXIS_VEC:
                raise KitError(f"{g.name(via_joint)}의 축 방향이 이상해요.")
            jattrs = {"name": via_joint, "type": jp["jtype"], "axis": AXIS_VEC[jp["axis"]],
                      "pos": _fmt(_vec(jp["pivot"], "축 위치", g, via_joint, 0.01)),
                      "damping": f"{max(0.0, _num(jp['damping'], '마찰', g, via_joint)):.6g}"}
            arm = _num(jp.get("armature", 0), "모터 회전자 관성", g, via_joint)
            if arm > 0:
                jattrs["armature"] = f"{arm:.6g}"
            ref = _num(jp.get("ref", 0), "기준 자세 각도", g, via_joint)
            if ref != 0:
                jattrs["ref"] = f"{ref * (0.01 if jp['jtype'] == 'slide' else 1):.6g}"
            ET.SubElement(el, "joint", **jattrs)
            joint_ids.append(via_joint)

        # 모양
        mass = _num(p["mass"], "무게", g, body_id)
        if mass <= 0:
            raise KitError(f"{g.name(body_id)}의 무게는 0보다 커야 해요.")
        size = _vec(p["size"], "크기", g, body_id, 0.01)
        gattrs = {"name": body_id + "_geom", "pos": _fmt(_vec(p["offset"], "모양 위치", g, body_id, 0.01)),
                  "euler": _fmt(_vec(p["rot"], "모양 회전", g, body_id)),
                  "rgba": _rgba(p.get("color")), "mass": f"{mass / 1000:.6g}"}
        shape = p["shape"]
        if shape != "mesh" and min(size) <= 0 and not (shape in ("cylinder", "capsule", "sphere")):
            raise KitError(f"{g.name(body_id)}의 크기는 0보다 커야 해요.")
        if shape == "box":
            gattrs.update(type="box", size=_fmt([s / 2 for s in size]))
        elif shape in ("cylinder", "capsule"):
            r, length = size[0] / 2, size[2]
            if r <= 0 or length <= 0:
                raise KitError(f"{g.name(body_id)}의 지름과 길이는 0보다 커야 해요.")
            half = length / 2 if shape == "cylinder" else max(length / 2 - r, 1e-4)  # 캡슐 길이는 둥근 끝 포함
            gattrs.update(type=shape, size=_fmt([r, half]))
        elif shape == "sphere":
            if size[0] <= 0:
                raise KitError(f"{g.name(body_id)}의 지름은 0보다 커야 해요.")
            gattrs.update(type="sphere", size=_fmt([size[0] / 2]))
        elif shape == "mesh":
            fname = p.get("mesh") or ""
            if fname not in meshes:
                raise KitError(f"{g.name(body_id)}의 3D 파일을 골라 주세요. (edukit/meshes 폴더의 STL 파일)")
            unit = MESH_SCALE.get(p.get("mesh_unit", "mm"), 0.001)
            path = meshes[fname].replace("\\", "/")
            ET.SubElement(asset, "mesh", name=body_id + "_mesh", file=path,
                          scale=_fmt([unit] * 3), inertia=_mesh_inertia_mode(path))
            gattrs.update(type="mesh", mesh=body_id + "_mesh")
        else:
            raise KitError(f"{g.name(body_id)}의 모양이 이상해요.")
        ET.SubElement(el, "geom", **gattrs)

        # 이 강체에 붙은 것들
        for dst, dport in g.dsts_of.get((body_id, "frame"), []):
            attach(dst, dport, el)

    def attach(dst, dport, xml_parent):
        t = g.blocks[dst]["type"]
        if t == "body" and dport == "parent":            # 조인트 없이 바로 고정
            add_body(dst, xml_parent, None)
        elif t == "joint" and dport == "parent":
            children = [d for d, dp in g.dsts_of.get((dst, "child"), []) if g.blocks[d]["type"] == "body"]
            if not children:
                warnings.append(f"{g.name(dst)} 조인트의 '자식' 칸에 강체가 없어요.")
            elif len(children) > 1:
                raise KitError(f"{g.name(dst)} 조인트의 '자식'에는 강체를 하나만 연결할 수 있어요.")
            else:
                add_body(children[0], xml_parent, dst)

    for dst, dport in g.dsts_of.get((ground["id"], "frame"), []):
        attach(dst, dport, world)

    for b in g.of_type("body"):
        if b["id"] not in visited:
            raise KitError(f"{g.name(b['id'])} 강체가 바닥까지 이어져 있지 않아요. '부모' 칸에 선을 연결해 주세요.")

    # 모터
    actuators = ET.SubElement(root, "actuator")
    motor_ids = []
    for m in g.of_type("motor"):
        targets = g.dsts_of.get((m["id"], "torque"), [])
        if not targets:
            warnings.append(f"{g.name(m['id'])} 모터의 '힘' 칸이 아무 조인트에도 연결되지 않았어요.")
            continue
        for jid, _ in targets:
            jp = g.blocks[jid]["params"]
            if jp["jtype"] == "fixed":
                raise KitError(f"{g.name(jid)}는 고정 조인트라서 모터를 달 수 없어요.")
            if jid not in joint_ids:
                raise KitError(f"{g.name(jid)} 조인트가 바닥까지 이어져 있지 않아요.")
            tmax = _num(m["params"]["max_torque"], "최대 토크", g, m["id"])
            ET.SubElement(actuators, "motor", name=f"{m['id']}_{jid}", joint=jid,
                          gear=f"{tmax:.6g}", ctrlrange="-1 1")
            motor_ids.append((m["id"], jid))

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode"), joint_ids, motor_ids, warnings


# ============================================================ 신호 블록 계산
SIGNAL_TYPES = {t for t, d in BLOCK_TYPES.items()
                if t not in ("ground", "body", "joint")}


def _wrap180(x):
    return (x + 180.0) % 360.0 - 180.0


class Controller:
    """신호 블록을 순서대로 계산해서 모터 명령과 스코프 기록을 만든다."""

    def __init__(self, g, model, joint_ids, motor_ids):
        self.g, self.model = g, model
        self.joint_ids = joint_ids
        self.motor_ids = motor_ids
        self.jinfo = {}
        for jid in joint_ids:
            j = model.joint(jid)
            slide = g.blocks[jid]["params"]["jtype"] == "slide"
            self.jinfo[jid] = (int(j.qposadr[0]), int(j.dofadr[0]), 100.0 if slide else 180.0 / math.pi)
        self.act_index = {mj: model.actuator(f"{mj[0]}_{mj[1]}").id for mj in motor_ids}
        self.order = self._sort()
        self.scopes = [b["id"] for b in g.of_type("scope")]
        self.reset()

    def _sort(self):
        """계산 순서 정하기 (위상 정렬). 조인트 센서를 거치지 않는 신호 고리는 계산할 수 없다."""
        g = self.g
        sig = [bid for bid, b in g.blocks.items() if b["type"] in SIGNAL_TYPES]
        deps = {bid: set() for bid in sig}
        for bid in sig:
            for name, kind, _ in BLOCK_TYPES[g.blocks[bid]["type"]]["inputs"]:
                src = g.src_of.get((bid, name))
                if src and src[0] in deps:
                    deps[bid].add(src[0])
        order, done = [], set()
        while len(order) < len(sig):
            ready = [b for b in sig if b not in done and deps[b] <= done]
            if not ready:
                loop = ", ".join(g.name(b) for b in sig if b not in done)
                raise KitError(f"신호가 빙글빙글 돌고 있어서 계산할 수 없어요: {loop}. "
                               "되먹임(피드백)은 조인트의 각도·각속도를 거쳐야 해요.")
            for b in ready:
                order.append(b)
                done.add(b)
        return order

    def reset(self):
        self.state = {bid: {} for bid in self.order}
        self.values = {}

    def _in(self, bid, port):
        src = self.g.src_of.get((bid, port))
        return self.values.get(src, 0.0) if src else 0.0

    def step(self, data, t):
        """제어 주기마다 호출: 센서 읽기 → 신호 계산 → data.ctrl 설정. 스코프 값 목록 반환."""
        v = self.values
        for jid, (qa, da, scale) in self.jinfo.items():
            v[(jid, "angle")] = float(data.qpos[qa]) * scale
            v[(jid, "vel")] = float(data.qvel[da]) * scale
        for bid in self.order:
            b = self.g.blocks[bid]
            p, t_, st = b["params"], b["type"], self.state[bid]
            f = lambda port: self._in(bid, port)
            fp = lambda k: float(p.get(k) or 0)
            if t_ == "const":
                v[(bid, "out")] = fp("value")
            elif t_ == "sine":
                v[(bid, "out")] = fp("amp") * math.sin(2 * math.pi * fp("freq") * t + math.radians(fp("phase"))) + fp("bias")
            elif t_ == "step":
                v[(bid, "out")] = fp("after") if t >= fp("time") else fp("before")
            elif t_ == "clock":
                v[(bid, "out")] = t
            elif t_ == "gain":
                v[(bid, "out")] = fp("k") * f("in")
            elif t_ == "sum":
                v[(bid, "out")] = sum((-1 if p.get(f"s{i}") == "-" else 1) * f(f"in{i}") for i in (1, 2, 3))
            elif t_ == "product":
                v[(bid, "out")] = f("in1") * f("in2")
            elif t_ == "sign":
                x = f("in")
                v[(bid, "out")] = 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)
            elif t_ == "abs":
                v[(bid, "out")] = abs(f("in"))
            elif t_ == "cos":
                v[(bid, "out")] = math.cos(math.radians(f("in")))
            elif t_ == "wrap":
                v[(bid, "out")] = _wrap180(f("in"))
            elif t_ == "sat":
                lo, hi = fp("lo"), fp("hi")
                v[(bid, "out")] = min(max(f("in"), min(lo, hi)), max(lo, hi))
            elif t_ == "pid":
                e = f("e")
                st["i"] = st.get("i", 0.0) + e * CTRL_DT
                de = (e - st["prev"]) / CTRL_DT if "prev" in st else 0.0
                st["prev"] = e
                v[(bid, "out")] = fp("kp") * e + fp("ki") * st["i"] + fp("kd") * de
            elif t_ == "switch":
                v[(bid, "out")] = f("in1") if f("in2") >= fp("threshold") else f("in3")
            elif t_ == "motor":
                v[(bid, "cmd")] = max(-1.0, min(1.0, f("cmd")))
        for mj, ai in self.act_index.items():
            data.ctrl[ai] = v[(mj[0], "cmd")]
        return [[self._in(s, f"in{i}") for i in (1, 2, 3)] for s in self.scopes]


# ============================================================ 모델 만들기 + 시뮬레이션
class Built:
    def __init__(self, raw_graph):
        self.graph = Graph(raw_graph)
        self.xml, joint_ids, motor_ids, self.warnings = build_mjcf(self.graph)
        try:
            self.model = mujoco.MjModel.from_xml_string(self.xml)
        except ValueError as e:
            raise KitError(f"MuJoCo가 모델을 만들지 못했어요: {e}")
        self.controller = Controller(self.graph, self.model, joint_ids, motor_ids)
        if not self.graph.of_type("scope"):
            self.warnings.append("스코프 블록이 없어서 그래프가 안 나와요. [보기]에서 스코프를 추가해 보세요.")

    def reset(self, data):
        """처음 자세 적용 + 제어기 초기화"""
        mujoco.mj_resetData(self.model, data)
        for jid, (qa, _, scale) in self.controller.jinfo.items():
            data.qpos[qa] = float(self.graph.blocks[jid]["params"].get("init") or 0) / scale
        mujoco.mj_forward(self.model, data)
        self.controller.reset()

    def step(self, data):
        """제어 1번 + 물리 5스텝. 스코프 값 반환."""
        rec = self.controller.step(data, data.time)
        for _ in range(CTRL_EVERY):
            mujoco.mj_step(self.model, data)
        if not np.all(np.isfinite(data.qpos)):
            raise KitError("시뮬레이션이 폭발했어요! 무게가 너무 작거나 모터 토크가 너무 큰지 확인해 보세요.")
        return rec


def _series_label(g, src):
    if src is None:
        return None
    bid, port = src
    b = g.blocks[bid]
    pname = next((lbl for n, _, lbl in BLOCK_TYPES[b["type"]]["outputs"] if n == port), port)
    unit = ""
    if b["type"] == "joint":
        slide = b["params"]["jtype"] == "slide"
        unit = {"angle": " (cm)" if slide else " (도)", "vel": " (cm/s)" if slide else " (도/s)"}.get(port, "")
    return f"{b['label']} {pname}{unit}" if len(BLOCK_TYPES[b["type"]]["outputs"]) > 1 else f"{b['label']}{unit}"


def simulate(raw_graph, duration):
    duration = float(duration)
    if not (0 < duration <= MAX_DURATION):
        raise KitError(f"시뮬레이션 시간은 0초보다 크고 {MAX_DURATION:.0f}초 이하여야 해요.")
    built = Built(raw_graph)
    g, m = built.graph, built.model
    d = mujoco.MjData(m)
    built.reset(d)
    n = int(round(duration / CTRL_DT))
    t_log, recs = [], []
    for _ in range(n):
        t_log.append(round(d.time, 4))
        recs.append(built.step(d))

    scopes = []
    for si, sid in enumerate(built.controller.scopes):
        series = []
        for i in (1, 2, 3):
            src = g.src_of.get((sid, f"in{i}"))
            if src:
                series.append({"label": _series_label(g, src),
                               "data": [round(r[si][i - 1], 5) for r in recs]})
        scopes.append({"id": sid, "title": g.blocks[sid]["params"].get("title") or g.blocks[sid]["label"],
                       "series": series})
    return {"ok": True, "t": t_log, "scopes": scopes, "xml": built.xml, "warnings": built.warnings}
