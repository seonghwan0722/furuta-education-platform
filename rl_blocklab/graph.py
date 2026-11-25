"""
graph.py — 블록 그래프(JSON) → 학습 설정 + 매 스텝 계산할 신호 프로그램
=======================================================================
그래프 JSON 형식 (에디터가 저장하는 형식):
  {"blocks": [{"id": "b1", "type": "plant", "x": 100, "y": 50, "params": {...}}, ...],
   "wires":  [{"src": ["b1", "height"], "dst": ["b5", "x"]}, ...]}

compile_graph(raw) → Spec
  spec.plant     : 진자 물리 설정 (dict)
  spec.rand      : 도메인 랜덤화 설정 (dict 또는 None)
  spec.agent     : PPO 하이퍼파라미터 (dict)
  spec.program   : 신호 블록 계산 순서 [(블록id, 종류, 파라미터, 입력 출처 목록)]
  spec.rewards   : [(블록id, 이름, 가중치, 입력 출처)]
  spec.terms     : [(블록id, 벌점, 입력 출처)]
  spec.scopes    : [(블록id, 제목, [(라벨, 출처), ...])]
"""
import math

from blocks import BLOCK_TYPES, default_params, port_kind

SIGNAL_BLOCKS = {"const", "gain", "sum", "product", "square", "abs", "cos", "sin", "compare", "limit"}
PLANT_SIGNALS = {"height", "theta", "theta_dot", "phi", "phi_dot", "u", "up_err"}


class GraphError(Exception):
    """학생에게 그대로 보여줄 수 있는 오류 메시지"""


def _num(v, what, label):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise GraphError(f"'{label}' 블록의 {what} 값이 숫자가 아니에요.")
    if not math.isfinite(x):
        raise GraphError(f"'{label}' 블록의 {what} 값이 이상해요.")
    return x


class Spec:
    pass


def compile_graph(raw):
    blocks = {}
    for b in raw.get("blocks", []):
        t = b.get("type")
        if t not in BLOCK_TYPES:
            raise GraphError(f"모르는 블록 종류예요: {t}")
        params = default_params(t)
        params.update(b.get("params") or {})
        blocks[b["id"]] = {"id": b["id"], "type": t,
                           "label": b.get("label") or BLOCK_TYPES[t]["label"], "params": params}

    # 입력 포트 하나에는 선 하나만 (마지막 선이 이김), 종류가 다른 포트끼리는 무시
    src_of = {}
    for w in raw.get("wires", []):
        (s, sp), (d, dp) = w["src"], w["dst"]
        if s not in blocks or d not in blocks:
            continue
        sk = port_kind(blocks[s]["type"], sp, "outputs")
        dk = port_kind(blocks[d]["type"], dp, "inputs")
        if sk is None or sk != dk:
            continue
        src_of[(d, dp)] = (s, sp)

    def of_type(t):
        return [b for b in blocks.values() if b["type"] == t]

    spec = Spec()
    spec.labels = {bid: b["label"] for bid, b in blocks.items()}

    # ---------------------------------------------------------------- 진자
    plants = of_type("plant")
    if len(plants) != 1:
        raise GraphError("'퓨루타 진자' 블록이 딱 하나 있어야 해요. 왼쪽 [환경]에서 꺼내 주세요.")
    plant = plants[0]
    pp, pl = plant["params"], plant["label"]
    spec.plant_id = plant["id"]
    spec.plant = {
        "model": pp["model"] if pp["model"] in ("cad", "rod") else "cad",
        "max_torque": _num(pp["max_torque"], "모터 최대 토크", pl),
        "pend_mass": _num(pp["pend_mass"], "진자 무게 배율", pl) / 100.0,
        "arm_damping": _num(pp["arm_damping"], "팔 마찰 배율", pl) / 100.0,
        "pend_damping": _num(pp["pend_damping"], "진자 마찰 배율", pl) / 100.0,
        "episode_s": _num(pp["episode_s"], "한 판 길이", pl),
        "ctrl_ms": _num(pp["ctrl_ms"], "제어 주기", pl),
        "init": pp["init"] if pp["init"] in ("down", "random", "up") else "down",
    }
    p = spec.plant
    if p["max_torque"] <= 0:
        raise GraphError("모터 최대 토크는 0보다 커야 해요.")
    if p["pend_mass"] <= 0:
        raise GraphError("진자 무게 배율은 0보다 커야 해요.")
    if p["arm_damping"] < 0 or p["pend_damping"] < 0:
        raise GraphError("마찰 배율은 0 이상이어야 해요.")
    if not (1 <= p["episode_s"] <= 60):
        raise GraphError("한 판 길이는 1~60초 사이로 정해 주세요.")
    if not (2 <= p["ctrl_ms"] <= 100):
        raise GraphError("제어 주기는 2~100 ms 사이로 정해 주세요.")

    # ---------------------------------------------------------------- 랜덤화 (진자 '랜덤화' 입력에 연결된 것만)
    spec.rand = None
    if (plant["id"], "rand") in src_of:
        rb = blocks[src_of[(plant["id"], "rand")][0]]
        rp, rl = rb["params"], rb["label"]
        spec.rand = {
            "mass": _num(rp["mass_pct"], "무게 변화", rl) / 100.0,
            "torque": _num(rp["torque_pct"], "모터 힘 변화", rl) / 100.0,
            "damping": _num(rp["damping_pct"], "마찰 변화", rl) / 100.0,
            "noise": math.radians(_num(rp["noise_deg"], "센서 잡음", rl)),
            "delay": int(round(_num(rp["delay_steps"], "명령 지연", rl))),
        }
        r = spec.rand
        if min(r["mass"], r["torque"], r["damping"], r["noise"], r["delay"]) < 0:
            raise GraphError("랜덤화 값은 0 이상이어야 해요.")
        if r["mass"] >= 1 or r["torque"] >= 1:
            raise GraphError("무게·모터 힘 변화는 100% 미만이어야 해요.")

    # ---------------------------------------------------------------- 에이전트
    agents = of_type("agent")
    spec.agent = None
    spec.agent_id = None
    if len(agents) > 1:
        raise GraphError("'PPO 에이전트' 블록은 하나만 놓아 주세요.")
    if agents:
        a = agents[0]
        ap, al = a["params"], a["label"]
        spec.agent_id = a["id"]
        spec.agent_wired = (src_of.get((a["id"], "obs")) == (plant["id"], "state")
                            and src_of.get((plant["id"], "u")) == (a["id"], "action"))
        hidden = [int(h) for h in str(ap["hidden"]).split(",") if h.strip()]
        spec.agent = {
            "total_steps": int(_num(ap["total_steps"], "총 학습 스텝", al)),
            "learning_rate": _num(ap["learning_rate"], "학습률", al),
            "gamma": _num(ap["gamma"], "할인율", al),
            "ent_coef": _num(ap["ent_coef"], "탐험 보너스", al),
            "hidden": hidden or [64, 64],
            "n_steps": int(_num(ap["n_steps"], "한 번에 모을 스텝", al)),
            "batch_size": int(_num(ap["batch_size"], "미니배치", al)),
            "n_epochs": int(_num(ap["n_epochs"], "반복 학습 횟수", al)),
            "gae_lambda": _num(ap["gae_lambda"], "GAE λ", al),
            "clip_range": _num(ap["clip_range"], "클립 범위", al),
            "n_envs": int(_num(ap["n_envs"], "동시에 돌릴 진자 수", al)),
            "seed": int(_num(ap["seed"], "랜덤 시드", al)),
        }
        g = spec.agent
        if not (1000 <= g["total_steps"] <= 20_000_000):
            raise GraphError("총 학습 스텝은 1,000 ~ 20,000,000 사이로 정해 주세요.")
        if not (0 < g["learning_rate"] < 1):
            raise GraphError("학습률은 0과 1 사이여야 해요 (보통 0.0003).")
        if not (0 < g["gamma"] < 1):
            raise GraphError("할인율 γ는 0과 1 사이여야 해요 (보통 0.99).")
        if not (1 <= g["n_envs"] <= 32) or g["n_steps"] < 16 or g["batch_size"] < 2 or g["n_epochs"] < 1:
            raise GraphError("에이전트의 고급 설정 값을 확인해 주세요.")
        if g["ent_coef"] < 0:
            raise GraphError("탐험 보너스는 0 이상이어야 해요.")

    # ---------------------------------------------------------------- 신호 계산 순서 (보상·종료·스코프에 필요한 것만)
    order, state = [], {}

    def need(src, path=()):
        """출처 (블록id, 포트)의 값을 계산할 수 있게 order 에 블록을 추가한다."""
        bid, port = src
        b = blocks[bid]
        if b["type"] == "plant":
            if port not in PLANT_SIGNALS:
                raise GraphError("진자의 '관측값 묶음'은 숫자 신호가 아니라서 계산 블록에 꽂을 수 없어요.")
            return
        if b["type"] not in SIGNAL_BLOCKS:
            raise GraphError(f"'{b['label']}' 블록의 출력은 숫자 신호가 아니에요.")
        if state.get(bid) == "done":
            return
        if state.get(bid) == "busy":
            raise GraphError(f"신호가 빙글빙글 돌아요 ('{b['label']}' 블록 근처). 되먹임 고리를 끊어 주세요.")
        state[bid] = "busy"
        ins = []
        for pname, _, _ in BLOCK_TYPES[b["type"]]["inputs"]:
            s = src_of.get((bid, pname))
            if s is not None:
                need(s)
            ins.append(s)
        params = dict(b["params"])
        if b["type"] == "sum":
            signs = str(params.get("signs", "+++")).replace(" ", "")
            if any(c not in "+-" for c in signs):
                raise GraphError(f"'{b['label']}' 블록의 부호에는 + 와 - 만 쓸 수 있어요.")
            params["signs"] = (signs + "+++")[:3]
        else:
            for k in ("value", "k", "threshold", "lo", "hi"):
                if k in params:
                    params[k] = _num(params[k], k, b["label"])
        order.append((bid, b["type"], params, ins))
        state[bid] = "done"

    spec.rewards, spec.terms, spec.scopes = [], [], []
    for b in blocks.values():
        t = b["type"]
        if t == "reward":
            s = src_of.get((b["id"], "x"))
            if s is None:
                continue
            need(s)
            spec.rewards.append((b["id"], str(b["params"]["name"]) or b["label"],
                                 _num(b["params"]["weight"], "가중치", b["label"]), s))
        elif t == "terminate":
            s = src_of.get((b["id"], "cond"))
            if s is None:
                continue
            need(s)
            spec.terms.append((b["id"], _num(b["params"]["penalty"], "벌점", b["label"]), s))
        elif t == "scope":
            chans = []
            for pname, _, plabel in BLOCK_TYPES["scope"]["inputs"]:
                s = src_of.get((b["id"], pname))
                if s is None:
                    continue
                need(s)
                chans.append((port_label(blocks, s), s))
            spec.scopes.append((b["id"], str(b["params"]["title"]) or "스코프", chans))
    spec.program = order

    # ---------------------------------------------------------------- 내보내기
    spec.export_name = None
    for b in of_type("export"):
        if spec.agent_id and src_of.get((b["id"], "policy")) == (spec.agent_id, "policy"):
            spec.export_name = "".join(c for c in str(b["params"]["name"]) if c.isalnum() or c in "_-") or "furuta_policy"
    return spec


def port_label(blocks, src):
    bid, port = src
    b = blocks[bid]
    for name, _, lab in BLOCK_TYPES[b["type"]]["outputs"]:
        if name == port:
            return lab if b["type"] == "plant" else f"{b['label']}"
    return port


def check_trainable(spec):
    """학습 시작 전 검사. 문제 없으면 경고 목록을 돌려준다."""
    if spec.agent is None:
        raise GraphError("'PPO 에이전트' 블록이 필요해요. 왼쪽 [학습]에서 꺼내 주세요.")
    if not spec.agent_wired:
        raise GraphError("진자의 '관측값 묶음' → 에이전트 '관측', 에이전트 '모터 명령' → 진자 '모터 명령'을 선으로 이어 주세요. "
                         "(Simulink의 되먹임 고리처럼 동그랗게 이어져야 해요)")
    if not spec.rewards:
        raise GraphError("'보상 항' 블록이 하나도 연결되어 있지 않아요. 보상이 없으면 에이전트가 무엇을 배울지 몰라요!")
    warnings = []
    if not any(w > 0 for _, _, w, _ in spec.rewards):
        warnings.append("양수 가중치의 보상 항이 없어요. 벌점만 있으면 '아무것도 안 하기'를 배울 수 있어요.")
    return warnings


# ==================================================================== 매 스텝 신호 계산
def eval_signals(program, plant_vals):
    """plant_vals: {'height': .., 'theta': .., ...}. 반환: {(블록id, 'y'): 값, ('P', 포트): 값}"""
    v = {}

    def get(src):
        if src is None:
            return 0.0
        bid, port = src
        if port in PLANT_SIGNALS and (bid, port) not in v:
            return plant_vals[port]
        return v[(bid, port)]

    for bid, t, p, ins in program:
        x = [get(s) for s in ins]
        if t == "const":
            y = p["value"]
        elif t == "gain":
            y = p["k"] * x[0]
        elif t == "sum":
            y = sum(xi if sg == "+" else -xi for xi, sg in zip(x, p["signs"]))
        elif t == "product":
            y = x[0] * x[1]
        elif t == "square":
            y = x[0] * x[0]
        elif t == "abs":
            y = abs(x[0])
        elif t == "cos":
            y = math.cos(x[0])
        elif t == "sin":
            y = math.sin(x[0])
        elif t == "compare":
            y = 1.0 if ((x[0] < p["threshold"]) if p["op"] == "<" else (x[0] > p["threshold"])) else 0.0
        elif t == "limit":
            y = min(max(x[0], p["lo"]), p["hi"])
        else:
            y = 0.0
        v[(bid, "y")] = float(y)
    return v, get
