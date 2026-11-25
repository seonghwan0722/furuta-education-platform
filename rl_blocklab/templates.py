"""
templates.py — 수업용 예제 블록 그래프 (레벨 0 ~ 3)
"""


class G:
    def __init__(self):
        self.blocks, self.wires, self.n = [], [], 0

    def add(self, t, x, y, label=None, **params):
        self.n += 1
        bid = f"b{self.n}"
        b = {"id": bid, "type": t, "x": x, "y": y, "params": params}
        if label:
            b["label"] = label
        self.blocks.append(b)
        return bid

    def wire(self, s, sp, d, dp):
        self.wires.append({"src": [s, sp], "dst": [d, dp]})

    def out(self):
        return {"blocks": self.blocks, "wires": self.wires}


def _core(g, steps=300000, rand=False):
    agent = g.add("agent", 60, 120, total_steps=steps)
    plant = g.add("plant", 360, 80)
    g.wire(agent, "action", plant, "u")
    g.wire(plant, "state", agent, "obs")
    if rand:
        r = g.add("randomize", 80, 360)
        g.wire(r, "rand", plant, "rand")
    ex = g.add("export", 60, 300 if not rand else 520)
    g.wire(agent, "policy", ex, "policy")
    return agent, plant


def _penalties(g, plant, wv=(-0.001, -0.00002, -0.01), y0=140):
    """속도·모터 힘 벌점 3개 (진자 속도², 팔 속도², 모터 명령²)"""
    names = [("theta_dot", "진자 속도 벌점"), ("phi_dot", "팔 속도 벌점"), ("u", "모터 힘 벌점")]
    for i, ((port, name), w) in enumerate(zip(names, wv)):
        sq = g.add("square", 700, y0 + 100 * i)
        g.wire(plant, port, sq, "x")
        g.wire(sq, "y", g.add("reward", 960, y0 + 100 * i, name=name, weight=w), "x")


def _basic_reward(g, plant):
    g.wire(plant, "height", g.add("reward", 960, 40, name="높이", weight=1), "x")
    sq = g.add("square", 700, 140)
    g.wire(plant, "u", sq, "x")
    g.wire(sq, "y", g.add("reward", 960, 140, name="모터 힘 벌점", weight=-0.01), "x")


def _scope(g, plant, y=470):
    sc = g.add("scope", 700, y, title="진자 높이와 모터 명령")
    g.wire(plant, "height", sc, "a")
    g.wire(plant, "u", sc, "b")
    sc2 = g.add("scope", 960, y, title="팔 각도")
    g.wire(plant, "phi", sc2, "a")


def level0():
    g = G()
    _, plant = _core(g)
    _scope(g, plant, 300)
    return g.out()


def level1():
    g = G()
    _, plant = _core(g)
    _basic_reward(g, plant)
    _scope(g, plant, 300)
    return g.out()


def original():
    """Capstone1/Mujoco/files/env.py 의 원래 보상 그대로 (팔이 가벼운 CAD 모델에선 잘 안 배워짐 → 토론 거리)"""
    g = G()
    _, plant = _core(g)
    g.wire(plant, "height", g.add("reward", 960, 40, name="높이", weight=1), "x")
    _penalties(g, plant, (-0.01, -0.001, -0.001))
    _scope(g, plant, 470)
    return g.out()


def _level2(g, plant):
    g.wire(plant, "height", g.add("reward", 960, 40, name="높이", weight=1), "x")
    _penalties(g, plant)
    cmp_ = g.add("compare", 700, 440, op="<", threshold=0.35)
    g.wire(plant, "up_err", cmp_, "x")
    g.wire(cmp_, "y", g.add("reward", 960, 440, name="서 있기 보너스", weight=1), "x")
    ab = g.add("abs", 700, 540)
    g.wire(plant, "phi", ab, "x")
    cmp2 = g.add("compare", 820, 540, op=">", threshold=6.28)
    g.wire(ab, "y", cmp2, "x")
    g.wire(cmp2, "y", g.add("terminate", 960, 540, penalty=50), "cond")
    _scope(g, plant, 640)


def level2():
    g = G()
    _, plant = _core(g, 400000)
    _level2(g, plant)
    return g.out()


def level3():
    g = G()
    _, plant = _core(g, 600000, rand=True)
    _level2(g, plant)
    return g.out()


TEMPLATES = [
    {"id": "level0", "title": "레벨 0 · 빈 보상 (직접 만들기)",
     "desc": "진자와 에이전트만 연결돼 있어요. 보상 항을 직접 만들어 연결해 보세요.", "make": level0},
    {"id": "level1", "title": "레벨 1 · 높이 보상 (가장 간단)",
     "desc": "진자가 높이 있을수록 점수 + 모터를 세게 쓰면 조금 벌점. 30만 스텝(약 5분)이면 스윙업과 균형을 배워요.", "make": level1},
    {"id": "level2", "title": "레벨 2 · 서 있기 보너스 + 벌점 + 팔 회전 제한",
     "desc": "속도 벌점을 더하고, 거의 섰을 때 보너스, 팔이 한 바퀴 넘게 돌면 판을 끝내요.", "make": level2},
    {"id": "original", "title": "토론 · env.py 원래 보상 (왜 안 될까?)",
     "desc": "원래 env.py 보상 그대로예요. 팔이 가벼운 CAD 모델에선 팔 속도 벌점이 너무 커서 잘 못 배워요. 가중치를 바꿔 고쳐 보세요.", "make": original},
    {"id": "level3", "title": "레벨 3 · Sim-to-Real (도메인 랜덤화)",
     "desc": "레벨 2 + 무게·모터 힘·마찰·센서 잡음 랜덤화. 라즈베리파이로 옮길 정책은 이걸로 학습하세요.", "make": level3},
]


def list_templates():
    return [{"id": t["id"], "title": t["title"], "desc": t["desc"], "graph": t["make"]()} for t in TEMPLATES]
