/* 환경(environment) 연결 계층.
 *
 * 앱의 나머지 코드는 "장치"에게 상태를 받고 모터 힘을 보낼 뿐, 그것이 화면 속 시뮬레이션인지
 * 책상 위 키트인지 거의 구분하지 않습니다. 다른 점은 하나입니다: 시뮬레이션은 앱이 매 순간 정책을 돌리고,
 * 실제 키트는 정책을 통째로 받아 키트 안에서 돌립니다(USB 지연이 제어에 끼어들지 않게).
 *
 * 상태는 모두 같은 모양입니다: { t, th, al, thd, ald, u, flags }
 *   th, al  : 팔·진자 각도 [rad], al = 0 이 아래로 매달림
 *   thd, ald: 각속도 [rad/s]
 *   u       : 실제로 들어간 모터 힘 (−1…1)
 *
 * 줄 단위 규약(v2)은 app/PROTOCOL.md, 키트 쪽 프로그램은 app/kit/kit_server.py 입니다.
 */
(function (PS) {
  "use strict";

  function Emitter() { this._h = {}; }
  Emitter.prototype.on = function (k, fn) { (this._h[k] = this._h[k] || []).push(fn); return this; };
  Emitter.prototype.emit = function (k, a) {
    (this._h[k] || []).forEach(function (fn) { fn(a); });
  };

  /* ── 화면 속 환경 ── */
  function SimDevice(C) {
    Emitter.call(this);
    this.kind = "sim";
    this.id = "sim";
    this.name = "시뮬레이션";
    this.C = C;
    this.sim = new PS.Furuta(C);
    this.connected = true;
    this.enabled = true;
    this.ctrlDt = this.sim.ctrlDt;
  }
  SimDevice.prototype = Object.create(Emitter.prototype);
  SimDevice.prototype.connect = function () { this.connected = true; this.emit("status", this); return Promise.resolve(); };
  SimDevice.prototype.disconnect = function () { return Promise.resolve(); };
  SimDevice.prototype.enable = function () { this.enabled = true; };
  SimDevice.prototype.disable = function () { this.enabled = false; };
  SimDevice.prototype.zero = function () { };
  SimDevice.prototype.reset = function (th, al, thd, ald) {
    this.sim.reset(th, al, thd, ald);
    return this.state();
  };
  SimDevice.prototype.state = function () {
    var s = this.sim;
    return { t: s.t, th: s.th, al: s.al, thd: s.thd, ald: s.ald, u: s.u, flags: s.dead ? 2 : 0 };
  };
  SimDevice.prototype.command = function (u) {
    this.sim.step(this.enabled ? u : 0);
    return this.state();
  };
  SimDevice.prototype.obs = function (out) { return this.sim.obs(out); };

  /* ── 실제 키트 (규약 v2, app/PROTOCOL.md) ──
   * 정책은 키트 안의 라즈베리파이가 50 Hz 로 직접 돌립니다. 앱은 가중치를 올리고(upload), 실행을 시키고(run),
   * 키트가 보내 주는 상태 줄로 그림과 그래프를 그립니다. USB 지연이 제어 지연이 되지 않습니다. */
  var CRC_T = null;
  function crc32(bytes) {
    var i, k, c;
    if (!CRC_T) {
      CRC_T = new Uint32Array(256);
      for (i = 0; i < 256; i++) {
        c = i;
        for (k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
        CRC_T[i] = c >>> 0;
      }
    }
    c = 0xFFFFFFFF;
    for (i = 0; i < bytes.length; i++) c = CRC_T[(c ^ bytes[i]) & 255] ^ (c >>> 8);
    return ((c ^ 0xFFFFFFFF) >>> 0).toString(16).padStart(8, "0");
  }

  /* 정책을 키트로 보낼 줄들로 바꿉니다. 값은 층마다 W(행 우선) 다음 b, float32 little-endian, base64. */
  function packPolicy(mlp) {
    var v = mlp.flatten(), dv = new DataView(new ArrayBuffer(v.length * 4)), i;
    for (i = 0; i < v.length; i++) dv.setFloat32(i * 4, v[i], true);
    var bytes = new Uint8Array(dv.buffer), crc = crc32(bytes), bin = "";
    for (i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    var b64 = btoa(bin);
    var sizes = [mlp.layers[0].cols].concat(mlp.layers.map(function (L) { return L.rows; }));
    var lines = ["P BEGIN " + v.length + " " + crc + " " + (mlp.act === Math.tanh ? "tanh" : "relu") + " " +
      (mlp.squash ? 1 : 0) + " " + sizes.join(",")];
    for (i = 0; i < b64.length; i += 180) lines.push("P " + b64.slice(i, i + 180));
    lines.push("P END");
    return { crc: crc, lines: lines, bytes: bytes.length };
  }

  function packController(config) {
    if (!config || config.schema !== 1 || config.kind !== 'furuta-classical' ||
        ['pid', 'lqr', 'lmpc'].indexOf(config.method) < 0) throw new Error('제어기 설정 형식을 확인해 주세요');
    var bytes = new TextEncoder().encode(JSON.stringify(config));
    if (!bytes.length || bytes.length > 32768) throw new Error('제어기 설정 크기는 32 KB 이하여야 합니다');
    var crc = crc32(bytes), bin = '';
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    var b64 = btoa(bin), lines = ['D BEGIN ' + bytes.length + ' ' + crc];
    for (var j = 0; j < b64.length; j += 180) lines.push('D ' + b64.slice(j, j + 180));
    lines.push('D END');
    return { crc: crc, lines: lines, bytes: bytes.length };
  }

  var ZERO = { t: 0, th: 0, al: 0, thd: 0, ald: 0, u: 0, flags: 0 };

  /* 키트 맞추기 값 줄: "L <stamp|NONE> k=v ..." 또는 "G OK <stamp> k=v ..." 의 OK 뒤부터. */
  function parseCal(p) {
    var out = { none: p[1] === "NONE", stamp: p[1] === "NONE" ? null : p[1] };
    p.slice(2).forEach(function (s) {
      var m = s.split("=");
      if (m.length === 2) out[m[0]] = m[1] === "-" ? null : +m[1];
    });
    return out;
  }

  function KitDevice(portPath) {
    Emitter.call(this);
    this.kind = "kit";
    this.id = portPath;
    this.name = portPath;
    this.port = portPath;
    this.connected = false;
    this.info = null;
    this.ctrlDt = 0.02;
    this.last = ZERO;
    this.polCrc = null;
    this.lastEnd = null;
    this.running = false;
    this._wait = [];
    this._h = this._h || {};
    this._run = null;
    this._cal = null;
    this._alive = null;
    this._helloTimer = null;
    this._connecting = false;
    this._uploading = false;
    this._linkFailed = false;
    this.controlCrc = null;
    this.controlMethod = null;
    this._runKind = null;
    this.cal = null;
    this.level = null;
    this.imu = { status: 'disconnected', message: '키트를 연결하면 수평을 확인합니다.' };
    this._imuTimer = null;
    this._imuPending = null;
    this._imuSerial = 0;
    this._imuLastSeq = -1;
    this._imuNextAt = 0;
    this._checking = false;
  }
  KitDevice.prototype = Object.create(Emitter.prototype);

  /* IMU는 대기 중에만 읽습니다. 실행/업로드 경로와 분리하고 오래된 응답은 버립니다. */
  KitDevice.prototype._imuState = function (status, message, sample) {
    this.imu = Object.assign({ status: status, message: message || '', fake: !!(this.info && this.info.fake) }, sample || {});
    this.emit('imu', this.imu);
  };
  KitDevice.prototype._pauseImu = function () {
    this._imuPending = null;
    if (this.info && this.info.imu1 && this.imu.status !== 'paused')
      this._imuState('paused', '키트 작업 중입니다. 작업이 끝나면 수평 측정을 다시 시작합니다.');
  };
  KitDevice.prototype._stopImu = function () {
    if (this._imuTimer) clearInterval(this._imuTimer);
    this._imuTimer = null;
    this._imuPending = null;
    this._imuState('disconnected', '연결이 끊어져 현재 기울기를 확인할 수 없습니다.');
  };
  KitDevice.prototype._startImu = function () {
    var self = this;
    if (this._imuTimer) clearInterval(this._imuTimer);
    this._imuTimer = null; this._imuPending = null; this._imuLastSeq = -1; this._imuNextAt = 0;
    if (!this.info || !this.info.imu1) {
      this._imuState('unsupported', 'Pi 수신기를 업데이트하면 MPU-9250 수평계를 사용할 수 있습니다.');
      return;
    }
    this._imuState('waiting', 'MPU-9250의 기울기를 읽는 중입니다.');
    this._imuTimer = setInterval(function () { self._imuTick(); }, 200);
    this._imuTick();
  };
  KitDevice.prototype._imuTick = function () {
    if (!this.connected || this._linkFailed || KitDevice.current !== this || !this.info || !this.info.imu1) return;
    if (this.running || this._uploading || this._checking) { this._pauseImu(); return; }
    var now = Date.now();
    if (this._imuPending) {
      if (now - this._imuPending.at <= 1200) return;
      this._imuPending = null; this._imuNextAt = now + 400;
      this._imuState('stale', '센서 응답이 늦습니다. 마지막 각도로 수평 여부를 판단하지 마세요.');
      return;
    }
    if (now < this._imuNextAt) return;
    var requestId = now.toString(36) + '-' + (++this._imuSerial).toString(36);
    this._imuPending = { id: requestId, at: now };
    this._write('U ' + requestId);
  };
  KitDevice.prototype._receiveImu = function (line) {
    if (!this.connected || !this.info || !this.info.imu1 || !this._imuPending) return;
    if (this.running || this._uploading || this._checking) { this._pauseImu(); return; }
    var sample;
    try { sample = JSON.parse(line.trim().slice(2)); } catch (_) {
      this._imuPending = null;
      this._imuState('unavailable', '센서 응답 형식을 확인할 수 없습니다.');
      return;
    }
    if (!sample || sample.request_id !== this._imuPending.id) return;
    var elapsed = Date.now() - this._imuPending.at;
    this._imuPending = null;
    if (elapsed > 1200 || elapsed < 0) { this._imuState('stale', '늦게 도착한 측정값입니다. 새 측정을 기다립니다.'); return; }
    if (['ok', 'moving', 'unavailable', 'paused'].indexOf(sample.status) < 0) {
      this._imuState('unavailable', '센서 상태를 확인할 수 없습니다.'); return;
    }
    var message = typeof sample.message === 'string' ? sample.message.slice(0,240) : '';
    if (sample.status === 'unavailable' || sample.status === 'paused') {
      this._imuState(sample.status, message); return;
    }
    var finite = function (n) { return typeof n === 'number' && Number.isFinite(n); };
    if (![sample.roll_deg, sample.pitch_deg, sample.tilt_deg, sample.accel_g, sample.gyro_dps].every(finite) ||
        Math.abs(sample.roll_deg) > 180 || Math.abs(sample.pitch_deg) > 90 || sample.tilt_deg < 0 || sample.tilt_deg > 180 ||
        sample.accel_g < 0 || sample.accel_g > 16 || sample.gyro_dps < 0 || sample.gyro_dps > 4000 ||
        !Number.isSafeInteger(sample.seq) || sample.seq < 0 || typeof sample.fake !== 'boolean' || sample.fake !== !!this.info.fake) {
      this._imuState('unavailable', '유효하지 않은 센서 측정값입니다. 배선과 수신기를 확인해 주세요.'); return;
    }
    if (sample.seq <= this._imuLastSeq) { this._imuState('stale', '새 센서 측정값을 기다립니다.'); return; }
    this._imuLastSeq = sample.seq;
    // 가속·회전 중의 중력 추정값으로 수평 완료를 표시하지 않습니다.
    var status = sample.status === 'ok' && (Math.abs(sample.accel_g - 1) > 0.08 || sample.gyro_dps > 3) ? 'moving' : sample.status;
    this._imuState(status, message, { roll_deg: sample.roll_deg, pitch_deg: sample.pitch_deg, tilt_deg: sample.tilt_deg,
      accel_g: sample.accel_g, gyro_dps: sample.gyro_dps, seq: sample.seq, fake: sample.fake, receivedAt: Date.now() });
  };

  KitDevice.installBridge = function () {
    if (KitDevice._wired || !window.studio) return;
    KitDevice._wired = true;
    window.studio.serial.onLine(function (line) {
      if (KitDevice.current) KitDevice.current._line(line);
    });
    window.studio.serial.onClosed(function () {
      var d = KitDevice.current;
      if (d) d._lost("연결이 끊어졌습니다");
    });
    window.studio.serial.onError(function (msg) {
      var d = KitDevice.current;
      if (d) d._lost(msg || "키트 통신 오류가 발생했습니다");
    });
  };

  KitDevice.prototype._write = function (line) {
    var self = this;
    if (KitDevice.current !== self || self._linkFailed) return Promise.resolve(false);
    return Promise.resolve().then(function () { return window.studio.serial.write(line); }).then(function (ok) {
      if (!ok) throw new Error("키트 연결이 닫혀 있습니다");
      return true;
    }).catch(function (error) {
      self._lost(error && error.message || "키트로 명령을 보내지 못했습니다");
      if (KitDevice.current === self) window.studio.serial.close().catch(function () {});
      return false;
    });
  };

  /* 조건에 맞는 줄이 올 때까지 기다립니다. */
  KitDevice.prototype._expect = function (test, ms, what) {
    var self = this;
    return new Promise(function (resolve, reject) {
      var w = { test: test, resolve: resolve, reject: reject };
      w.timer = setTimeout(function () {
        self._wait = self._wait.filter(function (x) { return x !== w; });
        reject(new Error(what + ": 키트가 응답하지 않습니다"));
      }, ms);
      self._wait.push(w);
    });
  };

  KitDevice.prototype._rejectWaiters = function (message) {
    var waiting = this._wait;
    this._wait = [];
    waiting.forEach(function (w) { clearTimeout(w.timer); w.reject(new Error(message)); });
    if (this._helloTimer) { clearInterval(this._helloTimer); this._helloTimer = null; }
  };

  KitDevice.prototype._lost = function (message) {
    if (this._linkFailed) return;
    this._linkFailed = true;
    this.connected = false;
    this._stopImu();
    this.polCrc = null;
    this.controlCrc = null;
    this.controlMethod = null;
    this._rejectWaiters(message);
    this._endCal(null, message);
    this._endRun({ reason: "link", steps: 0, detail: message });
    this.emit("status", this);
    this.emit("alert", { code: "closed", message: message });
  };

  KitDevice.prototype._endRun = function (end) {
    var r = this._run;
    if (this._alive) { clearInterval(this._alive); this._alive = null; }
    if (this._limit) { clearTimeout(this._limit); this._limit = null; }
    this._run = null;
    this._runKind = null;
    this.running = false;
    this.lastEnd = end.reason;
    if (r && r.onEnd) r.onEnd(end);
    this.emit("status", this);
  };

  KitDevice.prototype._line = function (line) {
    var p = line.trim().split(/\s+/), c = p[0], D = Math.PI / 180, r = this._run;
    if (!c) return;
    if (c === 'U') { this._receiveImu(line); return; }
    if (c === "T") {
      if (p.length !== 8 || !p.slice(1).every(function (value) { return value !== "" && Number.isFinite(Number(value)); })) {
        this.emit("alert", { code: "telemetry", message: "완전하지 않은 키트 상태 줄을 받았습니다" });
        return;
      }
      this.last = {
        t: +p[1] / 1000, th: +p[2] / 1000 * D, al: +p[3] / 1000 * D,
        thd: +p[4] / 1000 * D, ald: +p[5] / 1000 * D, u: +p[6] / 1000, flags: +p[7] | 0
      };
      if (r && r.onState) r.onState(this.last);
      return;
    }
    if (c === "I") {
      if (p.length < 6 || !Number.isFinite(+p[3]) || +p[3] <= 0 || !Number.isFinite(+p[4]) || +p[4] <= 0) return;
      this.info = { name: p[1], fw: p[2], hz: +p[3] || 50, tau_mNm: +p[4] || 0, v2: p[5] === "v2", fake: p.slice(6).indexOf("fake") >= 0, control1: p.slice(6).indexOf("control1") >= 0, imu1: p.slice(6).indexOf('imu1') >= 0 };
      this.name = p[1] || this.port;
      this.ctrlDt = 1 / this.info.hz;
    } else if (c === "K") {
      this.polCrc = p[2] && p[2] !== "-" ? p[2] : null;
      this.lastEnd = p[3] && p[3] !== "-" ? p[3] : null;
    } else if (c === "P" && p[1] === "OK") {
      this.polCrc = p[2];
    } else if (c === "M") {
      if (p[1] === "level" && p[2] === "ok") this.level = parseCal(["", "run"].concat(p.slice(3)));
      if (r && r.onMsg) r.onMsg(p[1], p.slice(2));
      if (this._cal && this._cal.onMsg) this._cal.onMsg(p[1], p.slice(2));
    } else if (c === "G") {
      if (p[1] === "OK") this._endCal(parseCal(p.slice(1)));
      else if (p[1] === "FAIL") this._endCal(null, (p[2] || "error") + " " + p.slice(3).join(" "));
      else if (this._cal && this._cal.onMsg) this._cal.onMsg(p[1], p.slice(2));
    } else if (c === "L") {
      this.cal = parseCal(p);
    } else if (c === 'V') {
      if (this._runKind !== 'control' || !r) return;
      try {
        var value = JSON.parse(line.slice(2));
        if (!value || typeof value !== 'object' || !Number.isFinite(value.t_ms) || value.t_ms < 0) return;
        if (r.onControl) r.onControl(value);
      } catch (_) { this.emit('alert', {code:'telemetry', message:'제어기 진단 줄을 읽지 못했습니다'}); }
      return;
    } else if (c === 'B' && p[1] === 'START') {
      if (this._runKind === 'control' && r && r.onMsg) r.onMsg('start', p.slice(2));
    } else if (c === 'B' && p[1] === 'END') {
      if (this._runKind === 'control') this._endRun({reason:p[2] || 'error', steps:+p[3] || 0, detail:p.slice(4).join(' ')});
    } else if (c === "R" && p[1] === "START") {
      if (this._runKind !== 'control' && r && r.onMsg) r.onMsg("start", []);
    } else if (c === "R" && p[1] === "END") {
      if (this._runKind !== 'control') this._endRun({ reason: p[2] || "error", steps: +p[3] || 0, detail: p.slice(4).join(" ") });
    } else if (c === "E" || c === "!") {
      var errorText = p.slice(1).join(" ");
      this.emit("alert", { code: p[1] || "", message: p.slice(2).join(" ") });
      if (c === "E" && (p[1] === "busy" || p[1] === "error")) this._rejectWaiters("키트: " + errorText);
      if (r && c === "E" && (p[1] === "error" || (this._runKind !== 'control' && (p[1] === "run" || (p[1] === "busy" && p[2] === "R"))))) this._endRun({ reason: "error", steps: 0, detail: errorText });
      if (r && this._runKind === 'control' && c === 'E' && (p[1] === 'control' || (p[1] === 'busy' && p[2] === 'B'))) this._endRun({reason:'error',steps:0,detail:errorText});
      if (this._cal && c === "E" && (p[1] === "error" || (p[1] === "busy" && p[2] === "G"))) this._endCal(null, errorText);
    }
    var hit = this._wait.filter(function (w) { return w.test(p); });
    if (hit.length) {
      this._wait = this._wait.filter(function (w) { return hit.indexOf(w) < 0; });
      hit.forEach(function (w) { clearTimeout(w.timer); w.resolve(p); });
    }
  };

  KitDevice.prototype.connect = function () {
    var self = this;
    if (self._connecting || self.connected) return Promise.reject(new Error("이미 연결 중이거나 연결된 키트입니다"));
    if (!window.studio || !window.studio.serial) return Promise.reject(new Error("설치한 앱에서 키트를 연결해 주세요"));
    KitDevice.installBridge();
    self._connecting = true;
    self._linkFailed = false;
    self.info = null;
    KitDevice.current = this;
    return window.studio.serial.open(this.port, 115200).then(function () {
      var hello = self._expect(function (p) { return p[0] === "I"; }, 4250, "연결 확인");
      self._write("H");
      self._helloTimer = setInterval(function () { self._write("H"); }, 250);
      return hello.then(function () { clearInterval(self._helloTimer); self._helloTimer = null; });
    }).then(function () {
      if (!self.info.v2) throw new Error("키트 프로그램이 오래된 버전입니다 (규약 v2 필요)");
      var w = self._expect(function (p) { return p[0] === "K"; }, 2000, "상태 읽기");
      self._write("Q");
      return w;
    }).then(function (p) {
      if (p[1] !== "idle") throw new Error("키트가 다른 실행을 하는 중입니다. 잠시 뒤에 다시 연결하세요");
      if (KitDevice.current !== self || self._linkFailed) throw new Error("키트 연결이 바뀌거나 끊어졌습니다");
      self.connected = true;
      self._connecting = false;
      self._startImu();
      self.emit("status", self);
    }).catch(function (e) {
      self._connecting = false;
      self.connected = false;
      self._stopImu();
      self._rejectWaiters(e.message);
      if (KitDevice.current !== self) throw e;
      KitDevice.current = null;
      return window.studio.serial.close().catch(function () {}).then(function () { throw e; });
    });
  };

  KitDevice.prototype.disconnect = function () {
    var self = this;
    this._stopImu();
    return Promise.resolve(this.running ? this._write("X") : null).then(function () {
      if (KitDevice.current === self) return window.studio.serial.close();
    }).then(function () {
      self.connected = false;
      self._linkFailed = true;
      self.polCrc = null;
      self.controlCrc = null;
      self.controlMethod = null;
      self._rejectWaiters("연결을 끊었습니다");
      self._endCal(null, "연결을 끊었습니다");
      if (KitDevice.current === self) KitDevice.current = null;
      self._endRun({ reason: "link", steps: 0, detail: "연결을 끊었습니다" });
    });
  };

  /* CRC는 가중치만 포함하므로 활성화·출력 변환·층 모양까지 일치하도록 매 실행 다시 올립니다. */
  KitDevice.prototype.upload = function (mlp) {
    var self = this, pk = packPolicy(mlp);
    if (!this.connected || this._linkFailed) return Promise.reject(new Error("키트를 먼저 연결해 주세요"));
    if (this.running) return Promise.reject(new Error("키트가 아직 실행 중입니다"));
    if (this._uploading) return Promise.reject(new Error("정책을 아직 보내고 있습니다. 전송이 끝난 뒤 다시 시작해 주세요"));
    this._uploading = true;
    this._pauseImu();
    var w = this._expect(function (p) {
      return (p[0] === "P" && p[1] === "OK") || (p[0] === "E" && p[1] === "policy");
    }, 20000, "정책 올리기");
    this._write(pk.lines);
    return w.then(function (p) {
      if (p[0] === "E") throw new Error("키트가 정책을 받지 않았습니다 (" + p.slice(2).join(" ") + ")");
      if (p[2] !== pk.crc) throw new Error("키트에 올라간 정책이 보낸 것과 다릅니다");
      self.polCrc = p[2];
      return p[2];
    }).finally(function () { self._uploading = false; });
  };

  KitDevice.prototype.uploadController = function (config) {
    var self = this;
    if (!this.connected || this._linkFailed || !this.info || !this.info.control1)
      return Promise.reject(new Error('Pi 수신기에 PID·LQR·LMPC 지원 업데이트가 필요합니다'));
    if (this.running || this._uploading) return Promise.reject(new Error('키트가 실행 또는 전송 중입니다'));
    if (this.info.hz !== 50 || this.info.tau_mNm !== 2520)
      return Promise.reject(new Error('키트의 제어 주기·토크 기준이 제어실험실과 다릅니다'));
    var pk;
    try { pk = packController(config); } catch (error) { return Promise.reject(error); }
    this.controlCrc = null; this.controlMethod = null; this._uploading = true;
    this._pauseImu();
    var wait = this._expect(function (p) { return (p[0] === 'D' && p[1] === 'OK') || (p[0] === 'E' && p[1] === 'control'); }, 20000, '제어기 보내기');
    this._write(pk.lines);
    return wait.then(function (p) {
      if (p[0] === 'E') throw new Error('Pi가 제어기 설정을 받지 않았습니다: ' + p.slice(2).join(' '));
      if (p[2] !== pk.crc || p[3] !== config.method) throw new Error('Pi에 저장된 제어기 설정이 다릅니다');
      self.controlCrc = pk.crc; self.controlMethod = config.method;
      return pk.crc;
    }).finally(function () { self._uploading = false; });
  };

  KitDevice.prototype.runController = function (seconds, crc, h) {
    if (!this.connected || this._linkFailed || !this.info.control1 || this.running || this._uploading)
      throw new Error('키트 연결과 제어기 전송 상태를 확인해 주세요');
    if (!Number.isFinite(seconds) || seconds < 1 || seconds > 20 || !crc || crc !== this.controlCrc)
      throw new Error('제어기 확인값 또는 실행 시간이 올바르지 않습니다');
    var self = this;
    this._run = h || {}; this._runKind = 'control'; this.running = true; this.last = ZERO;
    this._pauseImu();
    this._write('B ' + seconds + ' ' + crc);
    this._write('A');
    this._alive = setInterval(function () { self._write('A'); }, 500);
    this._limit = setTimeout(function () {
      self._write('X');
      self._lost('Pi 종료 응답이 없어 실물 상태를 확인할 수 없습니다');
      if (KitDevice.current === self) window.studio.serial.close().catch(function () {});
    }, (seconds + 180) * 1000);
    this.emit('status', this);
  };

  /* 키트에서 secs 초 동안 실행합니다. h: { onMsg(code, args), onState(st), onEnd({reason, steps, detail}) } */
  KitDevice.prototype.run = function (secs, h) {
    var self = this;
    if (!this.connected || this._linkFailed || this.running) throw new Error("키트 연결과 대기 상태를 확인해 주세요");
    if (!Number.isFinite(secs) || secs < 1 || secs > 30) throw new Error("실행 시간은 1~30초여야 합니다");
    this._run = h || {};
    this._runKind = 'policy';
    this.running = true;
    this._pauseImu();
    this.last = ZERO;
    this._write("R " + secs);
    this._write("A");
    this._alive = setInterval(function () { self._write("A"); }, 500);
    this._limit = setTimeout(function () {
      self._endRun({ reason: "link", steps: 0, detail: "키트가 끝났다고 알려 오지 않았습니다" });
    }, (secs + 60) * 1000);
    this.emit("status", this);
  };

  KitDevice.prototype.stop = function () {
    if (this.running) this._write("X");
  };

  /* 키트 점검: 모터를 움직이지 않고 CAN·모터 응답·진자 센서만 읽습니다. */
  KitDevice.prototype.check = function () {
    if (!this.connected || this._linkFailed) return Promise.reject(new Error("키트를 먼저 연결해 주세요"));
    if (this.running || this._uploading || this._checking) return Promise.reject(new Error('키트 작업이 끝난 뒤 점검해 주세요'));
    var self = this;
    this._checking = true; this._pauseImu();
    var w = this._expect(function (p) { return p[0] === "C"; }, 8000, "키트 점검");
    this._write("C");
    return w.then(function (p) {
      var out = { ok: p[1] === "OK", text: p.slice(2).join(" ") };
      if (out.ok) p.slice(2).forEach(function (kv) { var m = kv.split("="); out[m[0]] = +m[1]; });
      return out;
    }).finally(function () { self._checking = false; });
  };

  /* 키트에 남아 있는 마지막 키트 맞추기 값 (모터를 움직이지 않음). */
  KitDevice.prototype.calInfo = function () {
    if (!this.connected || this._linkFailed) return Promise.reject(new Error("키트를 먼저 연결해 주세요"));
    var self = this, w = this._expect(function (p) { return p[0] === "L"; }, 3000, "맞추기 값 읽기");
    this._write("L");
    return w.then(function () { return self.cal; });
  };

  /* 키트 맞추기 (모터가 움직입니다). 사용자가 확인 단추를 눌렀을 때만 부릅니다.
   * h: { onMsg(code, args) }. 끝나면 값({stamp, C, tilt, dir, J, Jm, Fp, Fm, b, T0, T0m, temp, ok}). */
  KitDevice.prototype.calibrate = function (h) {
    var self = this;
    if (!this.connected || this._linkFailed) return Promise.reject(new Error("키트를 먼저 연결해 주세요"));
    if (this.running) return Promise.reject(new Error("키트가 다른 일을 하는 중입니다"));
    return new Promise(function (resolve, reject) {
      self._cal = { onMsg: (h || {}).onMsg, resolve: resolve, reject: reject };
      self.running = true;
      self._pauseImu();
      self._write("G");
      self._write("A");
      self._alive = setInterval(function () { self._write("A"); }, 500);
      self._limit = setTimeout(function () { self._endCal(null, "키트가 끝났다고 알려 오지 않았습니다"); }, 180000);
      self.emit("status", self);
    });
  };

  KitDevice.prototype._endCal = function (cal, why) {
    var c = this._cal;
    if (!c) return;
    this._cal = null;
    if (this._alive) { clearInterval(this._alive); this._alive = null; }
    if (this._limit) { clearTimeout(this._limit); this._limit = null; }
    this.running = false;
    if (cal) { this.cal = cal; c.resolve(cal); } else c.reject(new Error(why || "키트 맞추기 실패"));
    this.emit("status", this);
  };

  KitDevice.prototype.state = function () { return this.last; };
  KitDevice.packPolicy = packPolicy;
  KitDevice.packController = packController;

  /* ── 한 번의 시험을 돌립니다. 시뮬레이션은 화면 주사율에 맞춰 밀고,
   *    실제 키트는 opt.policy 를 올린 뒤 장치가 보내 주는 상태에 맞춰 따라갑니다.
   *    끝나면 onDone(마지막 상태, end). end 는 키트일 때만 있고 { reason, steps, detail } 입니다. ── */
  function runEpisode(dev, controller, opt) {
    opt = opt || {};
    var secs = opt.seconds || 10;
    var onTick = opt.onTick || function () { };
    // Measurement and display have different clocks. Never drop control samples
    // when a hidden/slow window catches up several steps in one display frame.
    var onSample = opt.onSample || function () { }, lastSampleT = 0;
    var onDone = opt.onDone || function () { };
    var obs = new Float64Array(PS.OBS_N);
    var stop = false;
    function sample(st) {
      if (!Number.isFinite(st.t) || st.t <= lastSampleT) return;
      lastSampleT = st.t;
      if (onSample(st) === false) {
        stop = true;
        if (dev.kind !== "sim") dev.stop();
      }
    }

    if (dev.kind === "sim") {
      var prev = performance.now(), acc = 0, speed = opt.speed || 1;
      var endTime = secs - dev.ctrlDt * 1e-7; // Floating-point time must not add an extra control step.
      dev.reset(opt.th0 || 0, opt.al0 !== undefined ? opt.al0 : 0, 0, 0);
      /* 타이머로 밉니다. requestAnimationFrame 은 창이 가려지면 멈추거나 아주 느려져서 시험이 끝나지 않습니다.
       * 가려진 창은 타이머도 1초에 한 번으로 늦춰지므로, 밀린 시간을 1.2초까지 한 번에 따라잡게 둡니다. */
      var timer = setTimeout(function frame() {
        var now = performance.now();
        acc += Math.min(1.2, (now - prev) / 1000) * speed;
        prev = now;
        while (acc >= dev.ctrlDt && dev.sim.t < endTime && !stop && !dev.sim.dead) {
          dev.obs(obs);
          dev.command(controller(obs, dev.sim));
          acc -= dev.ctrlDt;
          sample(dev.state());
        }
        var st = dev.state();
        onTick(st);
        if (!stop && st.t < endTime && !dev.sim.dead) timer = setTimeout(frame, 16);
        else if (!stop) onDone(st);
      }, 16);
      return { cancel: function () { stop = true; clearTimeout(timer); } };
    }

    /* 실제 키트: 정책을 올리고, 실행을 시키고, 키트가 보내 주는 상태를 따라갑니다. */
    var ended = false;
    var fin = function (end) {
      if (ended) return;
      ended = true;
      if (!stop) onDone(dev.last, end);
    };
    var onMsg = opt.onMsg || function () { };
    onMsg("upload", []);
    dev.upload(opt.policy).then(function () {
      if (stop) return;
      dev.run(secs, {
        onMsg: function (code, args) { if (!stop) onMsg(code, args); },
        onState: function (st) { if (!stop) { sample(st); if (!stop) onTick(st); } },
        onEnd: fin
      });
    }).catch(function (e) {
      fin({ reason: "error", steps: 0, detail: String(e && e.message || e) });
    });
    return { cancel: function () { stop = true; dev.stop(); } };
  }

  PS.SimDevice = SimDevice;
  PS.KitDevice = KitDevice;
  PS.runEpisode = runEpisode;
})(window.PS = window.PS || {});
