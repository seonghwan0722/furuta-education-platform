"""
viewer.py — 3D 뷰어로 Rotary Pendulum 실시간 확인
==================================================
실행하면 창이 뜨고, pendulum이 흔들리는 걸 눈으로 볼 수 있음.
마우스로 회전, 스크롤로 줌.

키:
  ESC : 종료
  SPACE : 일시정지
  드래그: 카메라 회전
  스크롤: 줌
"""
import mujoco
import mujoco.viewer
import time
from env import XML_PATH

# 모델 로드 (env.py 의 XML_PATH = models/legacy_cad/test_sim.xml)
model = mujoco.MjModel.from_xml_path(XML_PATH)
data  = mujoco.MjData(model)

# 초기 조건: pendulum을 살짝 기울여둠
data.qpos[1] = 0.8

# passive viewer 열기 (사용자 제어)
with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()
    while viewer.is_running():
        step_start = time.time()

        # 물리 한 스텝 진행
        mujoco.mj_step(model, data)

        # 뷰어 동기화
        viewer.sync()

        # 실시간 재생 (너무 빠르지 않게)
        time_until_next = model.opt.timestep - (time.time() - step_start)
        if time_until_next > 0:
            time.sleep(time_until_next)
