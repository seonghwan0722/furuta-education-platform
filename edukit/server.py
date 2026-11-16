"""
server.py — 블록 코딩 교육 키트 서버
======================================
실행하면 브라우저에 블록 에디터가 열린다. (인터넷 없이 동작)
  python server.py            → http://localhost:8765

API (에디터가 호출)
  GET  /api/schema     블록 종류 정의
  GET  /api/meshes     사용할 수 있는 STL 파일 목록
  GET  /api/templates  예제 목록
  POST /api/run        {graph, duration} → 스코프 그래프 데이터 + MuJoCo XML
  POST /api/xml        {graph}           → MuJoCo XML
  POST /api/view       {graph}           → 3D 뷰어 창 띄우기 (viewer_run.py)
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

from blocks import BLOCK_TYPES, CATEGORIES
from kit_core import KitError, Built, list_meshes, simulate
from templates import list_templates

KIT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(KIT_DIR, "static")
PORT = int(os.environ.get("EDUKIT_PORT", "8765"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):          # 콘솔을 조용하게
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/schema":
            return self._json({"types": BLOCK_TYPES, "categories": CATEGORIES})
        if path == "/api/meshes":
            return self._json(sorted(list_meshes().keys()))
        if path == "/api/templates":
            return self._json(list_templates())
        return super().do_GET()

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            path = self.path.split("?")[0]
            if path == "/api/run":
                return self._json(simulate(req["graph"], req.get("duration", 10)))
            if path == "/api/xml":
                b = Built(req["graph"])
                return self._json({"ok": True, "xml": b.xml, "warnings": b.warnings})
            if path == "/api/view":
                Built(req["graph"])                                  # 먼저 오류가 없는지 확인
                fd, gpath = tempfile.mkstemp(prefix="edukit_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(req["graph"], f, ensure_ascii=False)
                subprocess.Popen([sys.executable, os.path.join(KIT_DIR, "viewer_run.py"), gpath], cwd=KIT_DIR)
                return self._json({"ok": True})
            return self._json({"ok": False, "error": "없는 주소예요."}, 404)
        except KitError as e:
            return self._json({"ok": False, "error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._json({"ok": False, "error": f"프로그램 오류: {type(e).__name__}: {e}"})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"블록 코딩 교육 키트 실행 중: {url}  (끄려면 Ctrl+C)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("종료")
