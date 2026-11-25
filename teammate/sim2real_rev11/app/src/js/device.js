/* 환경(environment) 연결 계층.
 *
 * 앱의 나머지 코드는 "장치"에게 상태를 받고 모터 힘을 보낼 뿐, 그것이 화면 속 시뮬레이션인지
 * 책상 위 키트인지 구분하지 않습니다. 하드웨어 구성이 아직 정해지지 않았으므로 이 경계를
 * 명확히 두었습니다. 나중에 Wi-Fi든 USB-CAN이든 여기 클래스 하나만 추가하면 됩니다.
 *
 * 상태는 모두 같은 모양입니다: { t, th, al, thd, ald, u, flags }
 *   th, al  : 팔·진자 각도 [rad], al = 0 이 아래로 매달림
 *   thd, ald: 각속도 [rad/s]
 *   u       : 실제로 들어간 모터 힘 (−1…1)
 *
 * 줄 단위 프로토콜은 app/PROTOCOL.md 에 적혀 있습니다.
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
    return { t: s.t, th: s.th, al: s.al, thd: s.thd, ald: s.ald, u: s.u, flags: 0 };
  };
  SimDevice.prototype.command = function (u) {
    this.sim.step(this.enabled ? u : 0);
    return this.state();
  };
  SimDevice.prototype.obs = function (out) { return this.sim.obs(out); };

  /* ── 실제 키트 ── */
  function SerialDevice(portPath) {
    Emitter.call(this);
    this.kind = "serial";
    this.id = portPath;
    this.name = portPath;
    this.port = portPath;
    this.connected = false;
    this.enabled = false;
    this.info = null;
    this.ctrlDt = 0.02;
    this.tauScale = 1000;
    this.last = { t: 0, th: 0, al: 0, thd: 0, ald: 0, u: 0, flags: 0 };
    this._t0 = null;
    this._uh = [0, 0];
  }
  SerialDevice.prototype = Object.create(Emitter.prototype);

  SerialDevice.installBridge = function () {
    if (SerialDevice._wired || !window.studio) return;
    SerialDevice._wired = true;
    window.studio.serial.onLine(function (line) {
      if (SerialDevice.current) SerialDevice.current._line(line);
    });
    window.studio.serial.onClosed(function () {
      var d = SerialDevice.current;
      if (d) { d.connected = false; d.emit("status", d); d.emit("alert", { code: "closed", message: "연결이 끊어졌습니다" }); }
    });
    window.studio.serial.onError(function (msg) {
      var d = SerialDevice.current;
      if (d) d.emit("alert", { code: "error", message: msg });
    });
  };

  SerialDevice.prototype._write = function (line) {
    return window.studio.serial.write(line);
  };

  SerialDevice.prototype._line = function (line) {
    var p = line.trim().split(/\s+/);
    if (!p.length) return;
    if (p[0] === "I") {
      this.info = { name: p[1], fw: p[2], hz: +p[3] || 50, tau_mNm: +p[4] || 1000 };
      this.name = p[1] || this.port;
      this.ctrlDt = 1 / this.info.hz;
      this.connected = true;
      this.emit("status", this);
      return;
    }
    if (p[0] === "T") {
      var ms = +p[1];
      if (this._t0 === null) this._t0 = ms;
      var D = Math.PI / 180;
      this.last = {
        t: (ms - this._t0) / 1000,
        th: +p[2] / 1000 * D,
        al: +p[3] / 1000 * D,
        thd: +p[4] / 1000 * D,
        ald: +p[5] / 1000 * D,
        u: +p[6] / this.tauScale,
        flags: +p[7] | 0
      };
      this.emit("state", this.last);
      return;
    }
    if (p[0] === "!") {
      this.emit("alert", { code: p[1] || "", message: p.slice(2).join(" ") });
    }
  };

  SerialDevice.prototype.connect = function () {
    var self = this;
    SerialDevice.installBridge();
    SerialDevice.current = this;
    return window.studio.serial.open(this.port, 115200).then(function () {
      return self._write("H");
    }).then(function () {
      return new Promise(function (resolve, reject) {
        var tries = 0;
        var iv = setInterval(function () {
          if (self.connected) { clearInterval(iv); resolve(); return; }
          if (++tries > 20) { clearInterval(iv); reject(new Error("장치가 응답하지 않습니다")); return; }
          self._write("H");
        }, 250);
      });
    }).then(function () {
      return self._write("S");
    });
  };

  SerialDevice.prototype.disconnect = function () {
    var self = this;
    return Promise.resolve(this._write("X")).then(function () {
      return self._write("D");
    }).then(function () {
      return window.studio.serial.close();
    }).then(function () {
      self.connected = false;
      if (SerialDevice.current === self) SerialDevice.current = null;
      self.emit("status", self);
    });
  };

  SerialDevice.prototype.enable = function () { this.enabled = true; this._write("E"); };
  SerialDevice.prototype.disable = function () { this.enabled = false; this._write("D"); };
  SerialDevice.prototype.zero = function () { this._write("Z"); this._t0 = null; };
  SerialDevice.prototype.reset = function () { this._t0 = null; return this.last; };
  SerialDevice.prototype.state = function () { return this.last; };
  SerialDevice.prototype.command = function (u) {
    u = Math.max(-1, Math.min(1, u));
    this._uh.push(u);
    if (this._uh.length > 2) this._uh.shift();
    var q = Math.round(u * 1000);
    this._write("U " + q);
    return this.last;
  };
  SerialDevice.prototype.obs = function (out) {
    out = out || new Float64Array(PS.OBS_N);
    var s = this.last, C = PS.MODEL;
    out[0] = Math.cos(s.th); out[1] = Math.sin(s.th);
    out[2] = Math.cos(s.al); out[3] = Math.sin(s.al);
    out[4] = s.thd / C.obs_scale.arm;
    out[5] = s.ald / C.obs_scale.pend;
    out[6] = this._uh[0];
    out[7] = this._uh[1];
    return out;
  };

  /* ── 한 번의 시험을 돌립니다. 시뮬레이션은 화면 주사율에 맞춰 밀고,
   *    실제 키트는 장치가 보내 주는 상태에 맞춰 따라갑니다. ── */
  function runEpisode(dev, controller, opt) {
    opt = opt || {};
    var secs = opt.seconds || 10;
    var onTick = opt.onTick || function () { };
    var onDone = opt.onDone || function () { };
    var obs = new Float64Array(PS.OBS_N);
    var stop = false;

    if (dev.kind === "sim") {
      var prev = performance.now(), acc = 0, speed = opt.speed || 1;
      dev.reset(opt.th0 || 0, opt.al0 !== undefined ? opt.al0 : 0, 0, 0);
      var raf = requestAnimationFrame(function frame(now) {
        acc += Math.min(0.1, (now - prev) / 1000) * speed;
        prev = now;
        while (acc >= dev.ctrlDt && dev.sim.t < secs && !stop) {
          dev.obs(obs);
          dev.command(controller(obs, dev.sim));
          acc -= dev.ctrlDt;
        }
        var st = dev.state();
        onTick(st);
        if (!stop && st.t < secs) raf = requestAnimationFrame(frame);
        else onDone(st);
      });
      return { cancel: function () { stop = true; cancelAnimationFrame(raf); } };
    }

    dev._uh = [0, 0];
    dev.zero();
    dev.enable();
    var h = function (st) {
      if (stop) return;
      if (st.t >= secs) { stop = true; dev.disable(); onDone(st); return; }
      dev.obs(obs);
      dev.command(controller(obs, null));
      onTick(st);
    };
    dev.on("state", h);
    return { cancel: function () { stop = true; dev.disable(); } };
  }

  PS.SimDevice = SimDevice;
  PS.SerialDevice = SerialDevice;
  PS.runEpisode = runEpisode;
})(window.PS = window.PS || {});
