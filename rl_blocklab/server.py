"""
server.py — RL 블록 실험실 서버
================================
실행하면 브라우저에 블록 에디터가 열린다. (인터넷 없이 동작)
  python server.py             → http://localhost:8770
  python server.py --no-browser

API (에디터가 호출)
  GET  /api/schema          블록 종류 정의
  GET  /api/templates       수업용 예제
  GET  /api/runs            학습 기록 목록 (학습 곡선 포함)
  GET  /api/train/status    지금 학습 상태
  POST /api/check   {graph}                     그래프 검사
  POST /api/train   {graph, name}               학습 시작
  POST /api/train/stop                          학습 멈추기 (지금까지 배운 정책은 저장)
  POST /api/rollout {graph, run_id, seconds, init}   시험 주행 (스코프·애니메이션 데이터)
  POST /api/view    {graph, run_id}             MuJoCo 3D 뷰어 창 띄우기 (이 컴퓨터에서)
  POST /api/export  {run_id}                    라즈베리파이용 파일 만들기
  GET  /api/download/<run_id>/<파일>             내보낸 zip 내려받기
  GET  /api/run/<run_id>/graph                  그 학습에 쓴 그래프
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from blocks import BLOCK_TYPES, CATEGORIES          # noqa: E402
from graph import GraphError, check_trainable, compile_graph   # noqa: E402
from templates import list_templates                 # noqa: E402
import trainer                                       # noqa: E402

STATIC_DIR = os.path.join(HERE, "static")
PORT = int(os.environ.get("BLOCKLAB_PORT", "8770"))
JOB = {"job": None}
LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/schema":
                return self._json({"types": BLOCK_TYPES, "categories": CATEGORIES})
            if path == "/api/templates":
                return self._json(list_templates())
            if path == "/api/runs":
                return self._json(trainer.list_runs())
            if path == "/api/train/status":
                job = JOB["job"]
                return self._json(job.info() if job else {"status": "idle"})
            if path.startswith("/api/run/") and path.endswith("/graph"):
                rid = path.split("/")[3]
                with open(trainer.run_path(rid, "graph.json"), encoding="utf-8") as f:
                    return self._json(json.load(f))
            if path.startswith("/api/download/"):
                _, _, _, rid, fname = path.split("/", 4)
                fpath = trainer.run_path(rid, os.path.basename(fname))
                with open(fpath, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(fname)}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        except FileNotFoundError as e:
            return self._json({"ok": False, "error": str(e)}, 404)
        return super().do_GET()

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            path = self.path.split("?")[0]
            if path == "/api/check":
                spec = compile_graph(req["graph"])
                try:
                    warns = check_trainable(spec)
                    trainable = True
                except GraphError as e:
                    warns, trainable = [str(e)], False
                return self._json({"ok": True, "trainable": trainable, "warnings": warns,
                                   "rewards": [n for _, n, _, _ in spec.rewards]})
            if path == "/api/train":
                with LOCK:
                    job = JOB["job"]
                    if job and job.status in ("starting", "running"):
                        return self._json({"ok": False, "error": "이미 학습 중이에요. 먼저 멈춰 주세요."})
                    job = trainer.TrainJob(req["graph"], req.get("name", ""))
                    job.start()
                    JOB["job"] = job
                return self._json({"ok": True, "id": job.id, "warnings": job.warnings})
            if path == "/api/train/stop":
                job = JOB["job"]
                if job:
                    job.stop_flag = True
                return self._json({"ok": True})
            if path == "/api/rollout":
                return self._json(trainer.rollout(req["graph"], req.get("run_id"), req.get("seconds"),
                                                  req.get("init")))
            if path == "/api/export":
                return self._json(trainer.export_pi(req["run_id"]))
            if path == "/api/view":
                compile_graph(req["graph"])
                fd, gpath = tempfile.mkstemp(prefix="blocklab_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(req, f, ensure_ascii=False)
                subprocess.Popen([sys.executable, os.path.join(HERE, "viewer_run.py"), gpath], cwd=HERE)
                return self._json({"ok": True})
            return self._json({"ok": False, "error": "없는 주소예요."}, 404)
        except GraphError as e:
            return self._json({"ok": False, "error": str(e)})
        except FileNotFoundError as e:
            return self._json({"ok": False, "error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._json({"ok": False, "error": f"프로그램 오류: {type(e).__name__}: {e}"})


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"RL 블록 실험실 실행 중: {url}  (끄려면 Ctrl+C)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("종료")


if __name__ == "__main__":
    main()
