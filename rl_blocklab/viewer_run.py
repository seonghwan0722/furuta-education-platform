"""
viewer_run.py — MuJoCo 3D 뷰어로 정책 실행 보기 (server.py 가 별도 창으로 띄움)
  python viewer_run.py <요청.json>      요청 = {"graph": ..., "run_id": ... 또는 null}
"""
import json
import sys
import time

import mujoco
import mujoco.viewer
import numpy as np

from furuta_env import FurutaBlockEnv
from graph import compile_graph
from trainer import load_model


def main(path):
    with open(path, encoding="utf-8") as f:
        req = json.load(f)
    env = FurutaBlockEnv(compile_graph(req["graph"]))
    model = load_model(req["run_id"]) if req.get("run_id") else None
    obs, _ = env.reset(seed=0)
    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        while viewer.is_running():
            t0 = time.time()
            act = model.predict(obs, deterministic=True)[0] if model else np.zeros(1)
            obs, _, term, trunc, _ = env.step(act)
            if term or trunc:
                obs, _ = env.reset()
            viewer.sync()
            time.sleep(max(0.0, env.ctrl_dt - (time.time() - t0)))


if __name__ == "__main__":
    main(sys.argv[1])
