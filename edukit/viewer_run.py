"""
viewer_run.py — 블록 다이어그램을 MuJoCo 3D 뷰어로 실시간 실행
=================================================================
에디터의 [3D로 보기] 버튼이 이 파일을 새 창으로 실행한다.
  python viewer_run.py 그래프.json

뷰어 조작: 드래그 = 카메라 회전, 스크롤 = 확대, Space = 일시정지,
          Backspace = 처음부터 다시, ESC/창 닫기 = 종료
"""
import json
import os
import sys
import time

import mujoco
import mujoco.viewer

from kit_core import Built, KitError

if __name__ == "__main__":
    gpath = sys.argv[1]
    with open(gpath, encoding="utf-8") as f:
        graph = json.load(f)
    try:
        os.remove(gpath)
    except OSError:
        pass
    try:
        built = Built(graph)
    except KitError as e:
        print("오류:", e)
        sys.exit(1)

    m = built.model
    d = mujoco.MjData(m)
    built.reset(d)
    with mujoco.viewer.launch_passive(m, d) as viewer:
        viewer.cam.distance = 1.0
        viewer.cam.lookat[:] = [0, 0, 0.3]
        viewer.cam.elevation = -20
        last_time = d.time
        while viewer.is_running():
            start = time.time()
            with viewer.lock():
                if d.time < last_time:              # 뷰어에서 Backspace(초기화)를 누른 경우
                    built.reset(d)
                try:
                    built.step(d)
                except KitError as e:
                    print("오류:", e)
                    built.reset(d)
                last_time = d.time
            viewer.sync()
            sleep = m.opt.timestep * 5 - (time.time() - start)
            if sleep > 0:
                time.sleep(sleep)
