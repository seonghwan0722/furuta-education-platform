"""
blocks.py — 블록 종류 정의 (에디터 화면과 시뮬레이터가 함께 사용)
===================================================================
블록 하나 = Simulink 블록 하나.
  inputs / outputs : 포트 목록 (이름, 종류, 화면 표시 이름)
      종류 "mech"   : 기구 연결 (바닥·강체·조인트를 이어 붙이는 선)
      종류 "signal" : 숫자 신호 (센서값, 제어 명령)
      종류 "torque" : 모터 → 조인트 (모터가 어느 조인트를 돌릴지)
  params : 속성 창에 나오는 설정값 (단위는 아이들이 쓰기 쉽게 cm, g, 도)
"""


def P(key, label, ptype, default, help="", options=None, adv=False, step=None):
    p = {"key": key, "label": label, "type": ptype, "default": default, "help": help}
    if options is not None:
        p["options"] = options
    if adv:
        p["adv"] = True
    if step is not None:
        p["step"] = step
    return p


SHAPES = [["box", "상자"], ["cylinder", "원기둥"], ["capsule", "캡슐(막대)"],
          ["sphere", "공"], ["mesh", "3D 파일 (STL)"]]
AXES = [["x", "x축"], ["y", "y축"], ["z", "z축"], ["-x", "-x축"], ["-y", "-y축"], ["-z", "-z축"]]
SIGNS = [["+", "+ 더하기"], ["-", "− 빼기"]]


BLOCK_TYPES = {
    # ------------------------------------------------------------------ 기구
    "ground": {
        "label": "바닥", "category": "기구", "icon": "🌍", "color": "#8d6e63",
        "desc": "세상의 바닥이에요. 모든 기구는 바닥에서부터 이어져야 해요.",
        "inputs": [],
        "outputs": [["frame", "mech", "붙이기"]],
        "params": [P("color", "바닥 색", "color", "#d9c8a9")],
    },
    "body": {
        "label": "강체", "category": "기구", "icon": "🧱", "color": "#ef6c00",
        "desc": "모양과 무게가 있는 물체예요. 부모 칸에 조인트나 바닥을 연결해요. "
                "조인트 없이 바로 붙이면 부모에 딱 고정돼요.",
        "inputs": [["parent", "mech", "부모"]],
        "outputs": [["frame", "mech", "붙이기"]],
        "params": [
            P("shape", "모양", "select", "box", options=SHAPES),
            P("size", "크기 (cm)", "vec3", [5, 5, 5],
              "상자: 가로·세로·높이 / 원기둥·캡슐: 지름·(안 씀)·길이 / 공: 지름 / 3D 파일: 안 씀"),
            P("mass", "무게 (g)", "number", 50, "강체 전체의 무게예요."),
            P("color", "색", "color", "#ff9800"),
            P("offset", "모양 위치 (cm)", "vec3", [0, 0, 0],
              "강체의 기준점(조인트 위치)에서 모양의 중심이 얼마나 떨어져 있는지예요. "
              "예: 아래로 매달린 30cm 막대는 z = -15"),
            P("rot", "모양 회전 (도)", "vec3", [0, 0, 0],
              "모양을 x·y·z축으로 돌려요. 원기둥·캡슐은 원래 z축(위아래) 방향이에요."),
            P("mesh", "3D 파일", "mesh", "", "모양이 '3D 파일'일 때 쓸 STL 파일이에요."),
            P("mesh_unit", "3D 파일 단위", "select", "mm",
              options=[["mm", "mm"], ["cm", "cm"], ["m", "m"]], adv=True),
        ],
    },
    "joint": {
        "label": "조인트", "category": "기구", "icon": "⚙️", "color": "#6d4c41",
        "desc": "부모와 자식 강체를 잇는 관절이에요. 회전·미끄럼·고정 중에 고를 수 있어요. "
                "각도와 각속도를 신호로 내보내요 (센서).",
        "inputs": [["parent", "mech", "부모"], ["torque", "torque", "모터"]],
        "outputs": [["child", "mech", "자식"], ["angle", "signal", "각도"], ["vel", "signal", "각속도"]],
        "params": [
            P("jtype", "종류", "select", "hinge",
              options=[["hinge", "회전"], ["slide", "미끄럼(직선)"], ["fixed", "고정"]]),
            P("axis", "축 방향", "select", "z", "회전(미끄럼)하는 축이에요.", options=AXES),
            P("pos", "위치 (cm)", "vec3", [0, 0, 0], "부모 강체의 기준점에서 이 조인트까지의 거리예요."),
            P("rot", "방향 (도)", "vec3", [0, 0, 0], "자식 강체를 처음에 얼마나 돌려서 붙일지예요.", adv=True),
            P("init", "처음 각도 (도)", "number", 0, "시뮬레이션 시작할 때 각도예요. (미끄럼이면 cm)"),
            P("damping", "마찰 (감쇠)", "number", 0.001,
              "클수록 빨리 멈춰요. 단위: N·m·s/rad", step=0.0001),
            P("armature", "모터 회전자 관성", "number", 0, "모터 안쪽 회전자의 관성이에요.", adv=True, step=0.00001),
            P("pivot", "축 위치 (cm, 자식 기준)", "vec3", [0, 0, 0],
              "CAD 모델처럼 회전축이 자식 강체의 기준점과 다를 때만 써요.", adv=True),
            P("ref", "기준 자세 각도 (도)", "number", 0,
              "CAD 모델을 불러왔을 때 그 자세가 몇 도인지예요. 보통 0이에요.", adv=True),
        ],
    },
    "motor": {
        "label": "모터", "category": "기구", "icon": "🔌", "color": "#7b1fa2",
        "desc": "조인트를 돌리는 모터예요. 명령 -1 ~ +1 을 받아서 최대 토크만큼 힘을 내요. "
                "힘 칸을 조인트의 '모터' 칸에 연결해요.",
        "inputs": [["cmd", "signal", "명령"]],
        "outputs": [["torque", "torque", "힘"]],
        "params": [P("max_torque", "최대 토크 (N·m)", "number", 0.03,
                     "명령이 1일 때 내는 힘이에요. 우리 키트 모터(2804)는 0.03", step=0.001)],
    },

    # ------------------------------------------------------------------ 신호 만들기
    "const": {
        "label": "상수", "category": "신호 만들기", "icon": "🔢", "color": "#1565c0",
        "desc": "항상 같은 숫자를 내보내요.",
        "inputs": [], "outputs": [["out", "signal", "값"]],
        "params": [P("value", "값", "number", 1)],
    },
    "sine": {
        "label": "사인파", "category": "신호 만들기", "icon": "〰️", "color": "#1565c0",
        "desc": "물결처럼 오르락내리락하는 신호예요. 크기 × sin(2π × 주파수 × 시간) + 중심값",
        "inputs": [], "outputs": [["out", "signal", "값"]],
        "params": [P("amp", "크기", "number", 0.5), P("freq", "주파수 (Hz, 1초에 몇 번)", "number", 0.5, step=0.05),
                   P("bias", "중심값", "number", 0, adv=True), P("phase", "시작 위치 (도)", "number", 0, adv=True)],
    },
    "step": {
        "label": "계단", "category": "신호 만들기", "icon": "📶", "color": "#1565c0",
        "desc": "정해진 시간이 되면 값이 확 바뀌어요.",
        "inputs": [], "outputs": [["out", "signal", "값"]],
        "params": [P("time", "바뀌는 시간 (초)", "number", 1), P("before", "처음 값", "number", 0),
                   P("after", "나중 값", "number", 1)],
    },
    "clock": {
        "label": "시계", "category": "신호 만들기", "icon": "⏱️", "color": "#1565c0",
        "desc": "지금 시간(초)을 내보내요.",
        "inputs": [], "outputs": [["out", "signal", "초"]], "params": [],
    },

    # ------------------------------------------------------------------ 계산
    "gain": {
        "label": "게인 (×)", "category": "계산", "icon": "✖️", "color": "#00838f",
        "desc": "들어온 신호에 숫자를 곱해요. 제어기의 '세기'를 정할 때 많이 써요.",
        "inputs": [["in", "signal", "입력"]], "outputs": [["out", "signal", "출력"]],
        "params": [P("k", "곱할 수", "number", 1, step=0.001)],
    },
    "sum": {
        "label": "더하기", "category": "계산", "icon": "➕", "color": "#00838f",
        "desc": "신호들을 더하거나 빼요. 빈 칸은 0으로 쳐요.",
        "inputs": [["in1", "signal", "입력1"], ["in2", "signal", "입력2"], ["in3", "signal", "입력3"]],
        "outputs": [["out", "signal", "합"]],
        "params": [P("s1", "입력1", "select", "+", options=SIGNS), P("s2", "입력2", "select", "+", options=SIGNS),
                   P("s3", "입력3", "select", "+", options=SIGNS)],
    },
    "product": {
        "label": "곱하기", "category": "계산", "icon": "✳️", "color": "#00838f",
        "desc": "두 신호를 곱해요.",
        "inputs": [["in1", "signal", "입력1"], ["in2", "signal", "입력2"]],
        "outputs": [["out", "signal", "곱"]], "params": [],
    },
    "sign": {
        "label": "부호", "category": "계산", "icon": "±", "color": "#00838f",
        "desc": "양수면 +1, 음수면 -1, 0이면 0을 내보내요.",
        "inputs": [["in", "signal", "입력"]], "outputs": [["out", "signal", "출력"]], "params": [],
    },
    "abs": {
        "label": "절댓값", "category": "계산", "icon": "|x|", "color": "#00838f",
        "desc": "음수를 양수로 바꿔요. (-3 → 3)",
        "inputs": [["in", "signal", "입력"]], "outputs": [["out", "signal", "출력"]], "params": [],
    },
    "cos": {
        "label": "코사인", "category": "계산", "icon": "cos", "color": "#00838f",
        "desc": "각도(도)의 코사인 값을 내보내요. 0도 → 1, 90도 → 0, 180도 → -1",
        "inputs": [["in", "signal", "각도"]], "outputs": [["out", "signal", "출력"]], "params": [],
    },
    "wrap": {
        "label": "각도 정리", "category": "계산", "icon": "🔄", "color": "#00838f",
        "desc": "각도를 -180 ~ 180도 사이로 바꿔요. 여러 바퀴 돈 각도(예: 370도 → 10도)를 정리할 때 써요.",
        "inputs": [["in", "signal", "각도"]], "outputs": [["out", "signal", "출력"]], "params": [],
    },
    "sat": {
        "label": "제한", "category": "계산", "icon": "⛔", "color": "#00838f",
        "desc": "신호가 너무 크거나 작지 않게 잘라요.",
        "inputs": [["in", "signal", "입력"]], "outputs": [["out", "signal", "출력"]],
        "params": [P("lo", "최소", "number", -1), P("hi", "최대", "number", 1)],
    },

    # ------------------------------------------------------------------ 제어
    "pid": {
        "label": "PID 제어기", "category": "제어", "icon": "🎛️", "color": "#2e7d32",
        "desc": "오차를 0으로 만들려고 노력하는 제어기예요. "
                "P: 지금 오차만큼 / I: 쌓인 오차만큼 / D: 오차가 변하는 빠르기만큼 힘을 내요.",
        "inputs": [["e", "signal", "오차"]], "outputs": [["out", "signal", "명령"]],
        "params": [P("kp", "P (비례)", "number", 0.01, step=0.001), P("ki", "I (적분)", "number", 0, step=0.001),
                   P("kd", "D (미분)", "number", 0, step=0.0001)],
    },
    "switch": {
        "label": "스위치", "category": "제어", "icon": "🔀", "color": "#2e7d32",
        "desc": "'조건' 신호가 기준값 이상이면 '위' 입력을, 아니면 '아래' 입력을 내보내요.",
        "inputs": [["in1", "signal", "위"], ["in2", "signal", "조건"], ["in3", "signal", "아래"]],
        "outputs": [["out", "signal", "출력"]],
        "params": [P("threshold", "기준값", "number", 0)],
    },

    # ------------------------------------------------------------------ 보기
    "scope": {
        "label": "스코프", "category": "보기", "icon": "📈", "color": "#c62828",
        "desc": "연결한 신호를 그래프로 보여줘요. 시뮬레이션을 실행하면 아래에 그래프가 나와요.",
        "inputs": [["in1", "signal", "선1"], ["in2", "signal", "선2"], ["in3", "signal", "선3"]],
        "outputs": [], "params": [P("title", "그래프 제목", "text", "그래프")],
    },
}

CATEGORIES = ["기구", "신호 만들기", "계산", "제어", "보기"]


def port_kind(btype, port, direction):
    """블록 종류 + 포트 이름 → 포트 종류 ('mech' / 'signal' / 'torque'), 없으면 None"""
    for name, kind, _ in BLOCK_TYPES[btype][direction]:
        if name == port:
            return kind
    return None


def default_params(btype):
    return {p["key"]: (list(p["default"]) if isinstance(p["default"], list) else p["default"])
            for p in BLOCK_TYPES[btype]["params"]}
