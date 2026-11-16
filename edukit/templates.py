"""
templates.py — 수업용 예제 (에디터의 '예제 불러오기' 목록)
==========================================================
① 진자 흔들어 보기          : 기구만 조립, 손으로 기울여서 놓았을 때 움직임 관찰
② 모터로 흔들기 (사인파)     : 모터에 사인파 명령 → 공진 주파수 찾기
③ 스윙업 + 균형 잡기         : 에너지 펌핑 + 균형 제어기 + 스위치 (도전 과제)
④ 우리 키트 (CAD 3D 모델)   : test 폴더의 실제 부품 STL로 조립한 키트 + ③ 제어기
"""


class _T:
    """예제 그래프를 코드로 조립하는 도우미"""

    def __init__(self):
        self.blocks, self.wires, self.n = [], [], 0

    def add(self, btype, label, x, y, **params):
        self.n += 1
        bid = f"b{self.n}"
        self.blocks.append({"id": bid, "type": btype, "label": label, "x": x, "y": y, "params": params})
        return bid

    def wire(self, src, sport, dst, dport):
        self.wires.append({"src": [src, sport], "dst": [dst, dport]})

    def graph(self):
        return {"blocks": self.blocks, "wires": self.wires}


# ------------------------------------------------------------------ 기본 도형 진자 (rotary_pendulum.xml 과 같은 크기)
def _simple_pendulum(t, pend_init=0.0):
    """바닥 - 기둥 - 팔 회전 - 팔 - 진자 회전 - 진자. (arm_joint, pend_joint) 반환"""
    ground = t.add("ground", "바닥", 40, 40)
    post = t.add("body", "기둥", 230, 40, shape="cylinder", size=[6, 6, 50], mass=500,
                 color="#555555", offset=[0, 0, 25], rot=[0, 0, 0])
    arm_j = t.add("joint", "팔 회전", 420, 40, jtype="hinge", axis="z", pos=[0, 0, 50],
                  init=0, damping=0.001, armature=0.001)
    arm = t.add("body", "팔", 620, 40, shape="capsule", size=[2, 2, 22], mass=50,
                color="#3380cc", offset=[10, 0, 0], rot=[0, 90, 0])
    pend_j = t.add("joint", "진자 회전", 810, 40, jtype="hinge", axis="x", pos=[20, 0, 0],
                   init=pend_init, damping=0.001, armature=0.001)
    pend = t.add("body", "진자", 1010, 40, shape="capsule", size=[1.6, 1.6, 31.6], mass=30,
                 color="#cc4d33", offset=[0, 0, -15], rot=[0, 0, 0])
    t.wire(ground, "frame", post, "parent")
    t.wire(post, "frame", arm_j, "parent")
    t.wire(arm_j, "child", arm, "parent")
    t.wire(arm, "frame", pend_j, "parent")
    t.wire(pend_j, "child", pend, "parent")
    return arm_j, pend_j


# ------------------------------------------------------------------ CAD 키트 (models/legacy_cad/test_sim.xml 과 같은 조립)
def _cad_pendulum(t, pend_init=0.0):
    """test 폴더 STL로 조립. 베어링 4개(각 2.55g)는 블록 수를 줄이려고 팔 홀더 무게에 합침."""
    ground = t.add("ground", "바닥", 40, 40)
    mount = t.add("joint", "받침 (고정)", 200, 40, jtype="fixed", pos=[0, 0, 30], rot=[90, 90, 0])
    motor_body = t.add("body", "모터 몸체 (2804)", 380, 40, shape="mesh", mesh="2804-body-v1.stl",
                       mesh_unit="mm", mass=65.2, color="#555555")
    arm_j = t.add("joint", "팔 회전", 570, 40, jtype="hinge", axis="z", rot=[90, 0, 0],
                  init=0, damping=0.0001, armature=0.00001)
    dc = t.add("body", "DC 홀더", 760, 40, shape="mesh", mesh="DC-holder-v4.stl", mass=10.3, color="#3380cc")
    fix = t.add("joint", "홀더 결합 (고정)", 940, 40, jtype="fixed", pos=[0, 0, -0.2])
    arm = t.add("body", "팔 홀더 (+베어링)", 1120, 40, shape="mesh", mesh="arm-holder-v8.stl",
                mass=25.3, color="#4a90d9")
    pend_j = t.add("joint", "진자 회전", 1300, 40, jtype="hinge", axis="x", pos=[0, 8, 2],
                   rot=[-180, 0, 90], pivot=[6.15, 0, 0], ref=-90,
                   init=pend_init, damping=0.00001)
    pipe = t.add("body", "진자 (벤딩 파이프)", 1490, 40, shape="mesh", mesh="bending-pipe-v5.stl",
                 mass=41.3, color="#cc4d33")
    fix2 = t.add("joint", "자석 결합 (고정)", 1670, 40, jtype="fixed", pos=[9.65, 0, 0], rot=[0, 90, 0])
    mag = t.add("body", "자석 홀더", 1850, 40, shape="mesh", mesh="magnet-holder-v1.stl",
                mass=3.75, color="#999999")
    for a, ap, b, bp in [(ground, "frame", mount, "parent"), (mount, "child", motor_body, "parent"),
                         (motor_body, "frame", arm_j, "parent"), (arm_j, "child", dc, "parent"),
                         (dc, "frame", fix, "parent"), (fix, "child", arm, "parent"),
                         (arm, "frame", pend_j, "parent"), (pend_j, "child", pipe, "parent"),
                         (pipe, "frame", fix2, "parent"), (fix2, "child", mag, "parent")]:
        t.wire(a, ap, b, bp)
    return arm_j, pend_j


# ------------------------------------------------------------------ 스윙업 + 균형 제어기 (블록으로 조립)
def _swingup_controller(t, arm_j, pend_j, max_torque, x0, k_swing, kp, kd, k_arm, k_armv, catch_deg):
    """
    흔들기(스윙업):  명령 = -k_swing × 부호(진자각속도 × cos(진자각도))
                    → 진자가 움직이는 방향에 맞춰 팔을 밀어서 점점 크게 흔든다 (그네 밀기)
    균형 잡기:       오차 = 각도정리(진자각도 - 180)
                    명령 = PID(오차) + k_arm × 각도정리(팔각도) + k_armv × 팔각속도
    스위치:          |오차| ≥ catch_deg 이면 흔들기, 아니면 균형 잡기
    """
    y1, y2, y3 = 330, 470, 610
    motor = t.add("motor", "모터", x0 + 1100, y2, max_torque=max_torque)
    t.wire(motor, "torque", arm_j, "torque")

    # 흔들기
    cosb = t.add("cos", "cos(진자)", x0, y1)
    prod = t.add("product", "속도×cos", x0 + 190, y1)
    sgn = t.add("sign", "방향", x0 + 380, y1)
    kswing = t.add("gain", "흔들기 세기", x0 + 570, y1, k=-k_swing)
    t.wire(pend_j, "angle", cosb, "in")
    t.wire(pend_j, "vel", prod, "in1")
    t.wire(cosb, "out", prod, "in2")
    t.wire(prod, "out", sgn, "in")
    t.wire(sgn, "out", kswing, "in")

    # 균형 잡기
    c180 = t.add("const", "목표 180도", x0, y2 + 60, value=180)
    err_sum = t.add("sum", "진자 - 목표", x0 + 190, y2, s1="+", s2="-", s3="+")
    err = t.add("wrap", "진자 오차", x0 + 380, y2)
    pid = t.add("pid", "진자 PID", x0 + 570, y2 + 30, kp=kp, ki=0, kd=kd)
    arm_wrap = t.add("wrap", "팔 각도 정리", x0 + 380, y3)
    karm = t.add("gain", "팔 제자리 게인", x0 + 570, y3 + 20, k=k_arm)
    karmv = t.add("gain", "팔 속도 게인", x0 + 570, y3 + 120, k=k_armv)
    bal = t.add("sum", "균형 명령", x0 + 760, y2 + 90)
    t.wire(pend_j, "angle", err_sum, "in1")
    t.wire(c180, "out", err_sum, "in2")
    t.wire(err_sum, "out", err, "in")
    t.wire(err, "out", pid, "e")
    t.wire(arm_j, "angle", arm_wrap, "in")
    t.wire(arm_wrap, "out", karm, "in")
    t.wire(arm_j, "vel", karmv, "in")
    t.wire(pid, "out", bal, "in1")
    t.wire(karm, "out", bal, "in2")
    t.wire(karmv, "out", bal, "in3")

    # 스위치
    abs_e = t.add("abs", "|오차|", x0 + 570, y2 - 50)
    sw = t.add("switch", "흔들기↔균형", x0 + 930, y2, threshold=catch_deg)
    t.wire(err, "out", abs_e, "in")
    t.wire(kswing, "out", sw, "in1")
    t.wire(abs_e, "out", sw, "in2")
    t.wire(bal, "out", sw, "in3")
    t.wire(sw, "out", motor, "cmd")

    # 보기
    sc1 = t.add("scope", "스코프: 진자", x0 + 1100, y1 - 20, title="진자 오차 (0이면 똑바로 섬)")
    sc2 = t.add("scope", "스코프: 팔·모터", x0 + 1100, y3 + 60, title="팔 각도와 모터 명령")
    t.wire(err, "out", sc1, "in1")
    t.wire(arm_wrap, "out", sc2, "in1")
    t.wire(sw, "out", sc2, "in2")
    return sw


# 제어 게인: 균형 게인은 LQR(Q=diag(1,10,0.1,0.1), R=1)로 계산, 흔들기 세기·기준값은 시뮬레이션으로 고름
# (tune_templates.py 로 다시 계산/확인할 수 있음)
SIMPLE_GAINS = dict(k_swing=0.2, kp=-0.11, kd=-0.022, k_arm=0.0085, k_armv=0.0068, catch_deg=30)
CAD_GAINS    = dict(k_swing=0.3, kp=-0.11, kd=-0.0099, k_arm=0.0078, k_armv=0.0043, catch_deg=30)


def t1_free_swing():
    t = _T()
    arm_j, pend_j = _simple_pendulum(t, pend_init=30)
    sc = t.add("scope", "스코프", 1010, 260, title="진자와 팔 각도")
    t.wire(pend_j, "angle", sc, "in1")
    t.wire(arm_j, "angle", sc, "in2")
    return t.graph()


def t2_sine_motor():
    t = _T()
    arm_j, pend_j = _simple_pendulum(t)
    sine = t.add("sine", "사인파", 240, 330, amp=0.3, freq=0.5)
    motor = t.add("motor", "모터", 440, 330, max_torque=1.0)
    t.wire(sine, "out", motor, "cmd")
    t.wire(motor, "torque", arm_j, "torque")
    sc = t.add("scope", "스코프", 1010, 300, title="진자 각도와 모터 명령")
    t.wire(pend_j, "angle", sc, "in1")
    t.wire(sine, "out", sc, "in2")
    return t.graph()


def t3_swingup():
    t = _T()
    arm_j, pend_j = _simple_pendulum(t, pend_init=5)
    _swingup_controller(t, arm_j, pend_j, max_torque=1.0, x0=40, **SIMPLE_GAINS)
    return t.graph()


def t4_cad_kit():
    t = _T()
    arm_j, pend_j = _cad_pendulum(t, pend_init=5)
    _swingup_controller(t, arm_j, pend_j, max_torque=0.03, x0=40, **CAD_GAINS)
    return t.graph()


TEMPLATES = [
    {"name": "① 진자 흔들어 보기", "duration": 10, "make": t1_free_swing,
     "desc": "진자를 30도 기울였다가 놓아요. 진자가 흔들릴 때 팔은 어떻게 움직일까요? "
             "'진자 회전' 조인트의 마찰이나 '진자' 무게를 바꿔 보세요."},
    {"name": "② 모터로 흔들기 (사인파)", "duration": 15, "make": t2_sine_motor,
     "desc": "모터를 사인파로 앞뒤로 돌려요. 사인파 주파수를 바꿔 가며 진자가 가장 크게 흔들리는 "
             "주파수(공진)를 찾아보세요. 힌트: 1Hz 근처!"},
    {"name": "③ 스윙업 + 균형 잡기 (도전)", "duration": 15, "make": t3_swingup,
     "desc": "그네를 밀듯이 진자를 흔들어 올린 뒤(스윙업), 위에서 넘어지지 않게 균형을 잡아요. "
             "'흔들기 세기', 'PID', '스위치 기준값'을 바꿔 보세요."},
    {"name": "④ 우리 키트 (CAD 3D 모델)", "duration": 15, "make": t4_cad_kit,
     "desc": "실제 키트 부품(STL)으로 조립한 모델이에요. 모터 최대 토크는 실제 모터 정격(0.03 N·m)이에요."},
]


def list_templates():
    return [{"name": tp["name"], "desc": tp["desc"], "duration": tp["duration"], "graph": tp["make"]()}
            for tp in TEMPLATES]
