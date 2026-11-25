"""
blocks.py — RL 블록 실험실의 블록 종류 정의 (화면과 학습 엔진이 함께 사용)
=========================================================================
블록 하나 = Simulink 블록 하나. 선(wire)은 같은 종류의 포트끼리만 이어진다.

포트 종류
  "signal" : 숫자 하나 (진자 각도, 속도, 계산 결과 …)  → 보상·종료·스코프 계산에 사용
  "state"  : 진자의 관측값 묶음 (진자 → 에이전트)
  "action" : 모터 명령 (에이전트 → 진자)
  "rand"   : 도메인 랜덤화 설정 (랜덤화 → 진자)
  "policy" : 학습된 정책 (에이전트 → 라즈베리파이 내보내기)
"""


def P(key, label, ptype, default, help="", options=None, adv=False, step=None, min=None, max=None):
    p = {"key": key, "label": label, "type": ptype, "default": default, "help": help}
    if options is not None:
        p["options"] = options
    if adv:
        p["adv"] = True
    if step is not None:
        p["step"] = step
    if min is not None:
        p["min"] = min
    if max is not None:
        p["max"] = max
    return p


CATEGORIES = [
    ["env", "환경", "#1e88e5"],
    ["agent", "학습", "#8e24aa"],
    ["math", "계산", "#00897b"],
    ["reward", "보상·종료", "#e53935"],
    ["view", "보기·내보내기", "#6d4c41"],
]

PLANT_OUTPUTS = [
    ["state", "state", "관측값 묶음"],
    ["height", "signal", "진자 높이 h"],
    ["theta", "signal", "진자 각 θ"],
    ["theta_dot", "signal", "진자 속도 θ̇"],
    ["phi", "signal", "팔 각 φ"],
    ["phi_dot", "signal", "팔 속도 φ̇"],
    ["u", "signal", "모터 명령 u"],
    ["up_err", "signal", "위까지 남은 각"],
]

BLOCK_TYPES = {
    # ------------------------------------------------------------------ 환경
    "plant": {
        "label": "퓨루타 진자", "category": "env", "icon": "🌀",
        "desc": "MuJoCo로 계산하는 회전 도립진자예요. 왼쪽에 모터 명령을 받고, 오른쪽으로 센서값을 내보내요. "
                "θ는 아래로 매달렸을 때 0, 똑바로 섰을 때 ±π(라디안)예요. "
                "진자 높이 h = −cos θ 는 아래 −1, 수평 0, 위 +1 이에요.",
        "inputs": [["u", "action", "모터 명령"], ["rand", "rand", "랜덤화"]],
        "outputs": PLANT_OUTPUTS,
        "params": [
            P("model", "모델", "select", "cad", options=[["cad", "우리 CAD 모델 (2804 모터)"], ["rod", "단순 막대 모델"]],
              help="CAD 모델은 팀의 실제 설계(test_sim.xml)를 그대로 쓴 것이에요."),
            P("max_torque", "모터 최대 토크 (N·m)", "number", 0.03, step=0.005, min=0.001, max=2,
              help="정책이 +1을 내면 이만큼의 힘으로 팔을 돌려요. 2804 짐벌 모터 ≈ 0.03 N·m. (막대 모델은 1 정도)"),
            P("pend_mass", "진자 무게 배율 (%)", "number", 100, step=5, min=20, max=500,
              help="진자(파이프+자석홀더)의 무게와 관성을 몇 %로 바꿀지예요. 무거우면 세우기 어려워져요."),
            P("arm_damping", "팔 마찰 배율 (%)", "number", 100, step=10, min=0, max=10000),
            P("pend_damping", "진자 마찰 배율 (%)", "number", 100, step=10, min=0, max=10000),
            P("episode_s", "한 판 길이 (초)", "number", 5, step=1, min=1, max=30,
              help="에피소드(한 판) 하나의 시간이에요. 이 시간이 지나면 처음 자세로 돌아가요."),
            P("ctrl_ms", "제어 주기 (ms)", "number", 10, step=2, min=2, max=50,
              help="정책이 몇 ms마다 모터 명령을 새로 정하는지예요. 라즈베리파이에서도 같은 주기로 돌려야 해요."),
            P("init", "시작 자세", "select", "down",
              options=[["down", "아래로 매달림 (스윙업 연습)"], ["random", "아무 자세 (랜덤)"], ["up", "거의 선 자세 (균형 연습)"]]),
        ],
    },
    "randomize": {
        "label": "도메인 랜덤화", "category": "env", "icon": "🎲",
        "desc": "매 판마다 진자의 무게·모터 힘·마찰을 조금씩 바꾸고 센서에 잡음을 넣어요. "
                "시뮬레이션과 실제 기계의 차이를 미리 겪게 해서, 라즈베리파이로 옮겼을 때 더 잘 버티게 해요 (Sim-to-Real).",
        "inputs": [],
        "outputs": [["rand", "rand", "랜덤화"]],
        "params": [
            P("mass_pct", "무게 변화 ± (%)", "number", 10, step=5, min=0, max=80),
            P("torque_pct", "모터 힘 변화 ± (%)", "number", 10, step=5, min=0, max=80),
            P("damping_pct", "마찰 변화 ± (%)", "number", 30, step=10, min=0, max=200),
            P("noise_deg", "각도 센서 잡음 (도)", "number", 0.3, step=0.1, min=0, max=10),
            P("delay_steps", "명령 지연 (제어 주기 수)", "number", 0, step=1, min=0, max=5,
              help="모터 명령이 몇 주기 늦게 들어가는지예요. 실제 통신·드라이버 지연을 흉내 내요."),
        ],
    },
    # ------------------------------------------------------------------ 학습
    "agent": {
        "label": "PPO 에이전트", "category": "agent", "icon": "🧠",
        "desc": "강화학습 두뇌예요. 관측값을 보고 모터 명령(−1~+1)을 정해요. "
                "보상 블록들의 합이 커지도록 신경망을 고쳐 나가요 (PPO 알고리즘, Stable-Baselines3).",
        "inputs": [["obs", "state", "관측"]],
        "outputs": [["action", "action", "모터 명령"], ["policy", "policy", "학습된 정책"]],
        "params": [
            P("total_steps", "총 학습 스텝", "number", 300000, step=50000, min=10000, max=5000000,
              help="시뮬레이션을 몇 번 움직여 보며 배울지예요. 많을수록 오래 걸리지만 더 잘 배워요."),
            P("learning_rate", "학습률", "number", 0.0003, step=0.0001, min=0.000001, max=0.01,
              help="한 번에 신경망을 얼마나 크게 고칠지예요. 너무 크면 불안정, 너무 작으면 느려요."),
            P("gamma", "할인율 γ", "number", 0.99, step=0.005, min=0.8, max=0.9999,
              help="미래 보상을 얼마나 중요하게 볼지예요. 1에 가까울수록 멀리 내다봐요."),
            P("ent_coef", "탐험 보너스", "number", 0.001, step=0.001, min=0, max=0.1,
              help="이것저것 시도해 보도록 하는 보너스(entropy)예요."),
            P("hidden", "신경망 크기", "select", "64,64",
              options=[["32,32", "작게 (32×32)"], ["64,64", "보통 (64×64)"], ["128,128", "크게 (128×128)"]],
              help="라즈베리파이에서 돌릴 신경망 크기예요. 작을수록 빠르게 계산돼요."),
            P("n_steps", "한 번에 모을 스텝", "number", 2048, step=256, min=128, max=16384, adv=True),
            P("batch_size", "미니배치", "number", 64, step=32, min=16, max=4096, adv=True),
            P("n_epochs", "반복 학습 횟수 (epoch)", "number", 10, step=1, min=1, max=50, adv=True),
            P("gae_lambda", "GAE λ", "number", 0.95, step=0.01, min=0.5, max=1, adv=True),
            P("clip_range", "클립 범위", "number", 0.2, step=0.05, min=0.05, max=0.5, adv=True),
            P("n_envs", "동시에 돌릴 진자 수", "number", 4, step=1, min=1, max=16, adv=True),
            P("seed", "랜덤 시드", "number", 0, step=1, min=0, max=99999, adv=True),
        ],
    },
    # ------------------------------------------------------------------ 계산
    "const": {
        "label": "상수", "category": "math", "icon": "🔢",
        "desc": "항상 같은 숫자를 내보내요.",
        "inputs": [], "outputs": [["y", "signal", "출력"]],
        "params": [P("value", "값", "number", 1, step=0.1)],
    },
    "gain": {
        "label": "게인 ×k", "category": "math", "icon": "✖️",
        "desc": "입력에 k를 곱해요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "출력"]],
        "params": [P("k", "k", "number", 1, step=0.1)],
    },
    "sum": {
        "label": "더하기", "category": "math", "icon": "➕",
        "desc": "입력들을 부호에 맞춰 더해요. 비어 있는 입력은 0이에요.",
        "inputs": [["a", "signal", "a"], ["b", "signal", "b"], ["c", "signal", "c"]],
        "outputs": [["y", "signal", "출력"]],
        "params": [P("signs", "부호 (a b c)", "text", "+++", help="예: '+-+' 이면 a − b + c")],
    },
    "product": {
        "label": "곱하기", "category": "math", "icon": "✳️",
        "desc": "두 입력을 곱해요.",
        "inputs": [["a", "signal", "a"], ["b", "signal", "b"]], "outputs": [["y", "signal", "출력"]],
        "params": [],
    },
    "square": {
        "label": "제곱 x²", "category": "math", "icon": "²",
        "desc": "입력을 제곱해요. 부호와 상관없이 크기에 벌점을 줄 때 많이 써요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "출력"]], "params": [],
    },
    "abs": {
        "label": "절댓값 |x|", "category": "math", "icon": "📏",
        "desc": "입력의 크기만 남겨요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "출력"]], "params": [],
    },
    "cos": {
        "label": "cos", "category": "math", "icon": "〰️",
        "desc": "cos(입력). 입력은 라디안이에요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "출력"]], "params": [],
    },
    "sin": {
        "label": "sin", "category": "math", "icon": "∿",
        "desc": "sin(입력). 입력은 라디안이에요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "출력"]], "params": [],
    },
    "compare": {
        "label": "비교", "category": "math", "icon": "⚖️",
        "desc": "조건이 맞으면 1, 아니면 0을 내보내요. 예: '위까지 남은 각 < 0.35' → 거의 섰을 때 1.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "참(1)/거짓(0)"]],
        "params": [P("op", "조건", "select", "<", options=[["<", "x < 기준"], [">", "x > 기준"]]),
                   P("threshold", "기준값", "number", 0.35, step=0.05)],
    },
    "limit": {
        "label": "제한", "category": "math", "icon": "🧱",
        "desc": "입력을 최솟값~최댓값 사이로 잘라요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [["y", "signal", "출력"]],
        "params": [P("lo", "최솟값", "number", -1, step=0.1), P("hi", "최댓값", "number", 1, step=0.1)],
    },
    # ------------------------------------------------------------------ 보상·종료
    "reward": {
        "label": "보상 항", "category": "reward", "icon": "🏆",
        "desc": "매 순간 '가중치 × 입력'만큼 점수를 줘요. 보상 항 블록을 여러 개 놓으면 모두 더해져요. "
                "가중치가 음수면 벌점이에요. 학습 결과 화면에서 항마다 점수를 따로 볼 수 있어요.",
        "inputs": [["x", "signal", "입력"]], "outputs": [],
        "params": [P("name", "이름", "text", "보상"), P("weight", "가중치", "number", 1, step=0.001)],
    },
    "terminate": {
        "label": "판 끝내기", "category": "reward", "icon": "🛑",
        "desc": "입력이 1(참)이 되면 그 판을 바로 끝내고 벌점을 줘요. 예: 팔이 너무 많이 돌면 멈추기.",
        "inputs": [["cond", "signal", "조건"]], "outputs": [],
        "params": [P("penalty", "벌점", "number", 10, step=1, min=0)],
    },
    # ------------------------------------------------------------------ 보기·내보내기
    "scope": {
        "label": "스코프", "category": "view", "icon": "📈",
        "desc": "연결한 신호를 시험 주행 그래프로 보여줘요 (Simulink Scope와 같아요).",
        "inputs": [["a", "signal", "1"], ["b", "signal", "2"], ["c", "signal", "3"]], "outputs": [],
        "params": [P("title", "제목", "text", "스코프")],
    },
    "export": {
        "label": "라즈베리파이로", "category": "view", "icon": "🍓",
        "desc": "학습된 정책을 라즈베리파이에서 돌릴 수 있게 numpy 파일 + 실행 스크립트로 내보내요. "
                "라즈베리파이에는 numpy만 있으면 돼요 (PyTorch 필요 없음).",
        "inputs": [["policy", "policy", "정책"]], "outputs": [],
        "params": [P("name", "내보낼 이름", "text", "furuta_policy")],
    },
}


def default_params(btype):
    return {p["key"]: p["default"] for p in BLOCK_TYPES[btype]["params"]}


def port_kind(btype, port, side):
    for name, kind, _ in BLOCK_TYPES[btype][side]:
        if name == port:
            return kind
    return None
