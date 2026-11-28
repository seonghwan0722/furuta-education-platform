/* Passive base leveling. This view never sends a motion command or redefines zero. */
(function (PS) {
  'use strict';
  var TARGET_KEY = 'ps-base-level-target-v1', FRESH_MS = 1600, HOLD_MS = 2000, nextId = 0;
  var finite = function (v) { return typeof v === 'number' && Number.isFinite(v); };
  function savedTarget(fallback) {
    try { var v = +localStorage.getItem(TARGET_KEY); if ([0.5, 1, 2].indexOf(v) >= 0) return v; } catch (_) { }
    return fallback || 1;
  }
  function ImuLevelPanel(host, options) {
    options = options || {};
    this.host = host; this.target = savedTarget(); this.sample = null; this.connected = false; this.onState = options.onState;
    this.busy = false; this.first = null; this.lastGood = null; this.lastSeq = null;
    var selectId = 'imu-target-' + (++nextId);
    host.innerHTML = '<section class="imu-level' + (options.compact ? ' imu-level-compact' : '') + '" data-state="disconnected" aria-label="받침 수평 맞추기">' +
      '<div class="imu-level-heading"><div><span class="imu-eyebrow">연결 후 첫 준비</span><h3>받침을 수평으로 맞춰 주세요</h3></div><span class="imu-source">MPU-9250 · 대기</span></div>' +
      '<p class="imu-level-lead">받침을 조금씩 조정하고, 손을 뗀 뒤 각도를 확인하세요. 이 수평계는 모터 명령을 보내지 않습니다.</p>' +
      '<div class="imu-level-body"><div class="imu-gauge"><svg viewBox="0 0 180 180" aria-hidden="true">' +
      '<circle cx="90" cy="90" r="66" class="imu-gauge-disc"/><path d="M24 90h132M90 24v132" class="imu-crosshair"/>' +
      '<circle cx="90" cy="90" r="13.2" class="imu-target-ring"/><circle cx="90" cy="90" r="3" class="imu-center"/>' +
      '<text x="90" y="15" text-anchor="middle">+피치</text><text x="159" y="94">+롤</text>' +
      '<circle cx="90" cy="90" r="8" class="imu-bubble" visibility="hidden"/></svg><span>중앙에 가까울수록 수평 · 눈금 ±5°</span></div>' +
      '<div class="imu-readings"><div class="imu-total"><span>전체 기울기</span><strong class="imu-angle-total">—</strong></div>' +
      '<div class="imu-axis-values"><div><span>앞뒤 · 피치</span><b class="imu-angle-pitch">—</b></div><div><span>좌우 · 롤</span><b class="imu-angle-roll">—</b></div></div>' +
      '<label class="imu-target-label" for="' + selectId + '">조정 목표<select class="imu-target" id="' + selectId + '"><option value="0.5">0.5° 이내</option><option value="1">1° 이내</option><option value="2">2° 이내</option></select></label></div></div>' +
      '<div class="imu-feedback"><span class="imu-level-status" role="status" aria-live="polite">키트 연결을 기다립니다</span><p class="imu-level-hint">Pi를 연결하면 센서 각도를 계속 확인합니다.</p><div class="imu-hold-track" aria-hidden="true"><span class="imu-hold-fill"></span></div></div>' +
      '<details class="imu-mount-help"><summary>센서 장착 방향과 각도의 의미</summary><p>MPU-9250을 움직이지 않는 받침에 평행하게 고정하세요. 진자나 회전 팔에 붙이면 받침의 기울기를 잴 수 없습니다. 기준 축은 +Z 위, +X 앞, +Y 왼쪽입니다. 다르게 장착했다면 Pi의 축 설정을 맞춰 주세요.</p><p>전체 기울기는 중력 방향에서 계산한 받침의 기울기입니다. 앞뒤·좌우 두 값 각각의 한계가 아니라, 전체 기울기를 목표와 비교합니다. 현재 자세를 0°로 덮어쓰지 않습니다.</p><p>이 목표는 설치 조정을 돕는 기준입니다. 센서 오차를 포함한 실제 수평도와 제어 안정성을 보증하는 값은 아닙니다. 기존 ‘키트 맞추기’는 팔을 움직이는 별도 과정입니다.</p></details></section>';
    this.el = host.firstElementChild;
    this.select = this.el.querySelector('.imu-target'); this.select.value = String(this.target);
    var self = this;
    this.select.addEventListener('change', function () {
      self.target = +self.select.value; self.resetHold();
      try { localStorage.setItem(TARGET_KEY, String(self.target)); } catch (_) { }
      self.render();
    });
    this.timer = setInterval(function () { self.render(); }, 250);
    this.render();
  }
  ImuLevelPanel.prototype.resetHold = function () { this.first = null; this.lastGood = null; this.lastSeq = null; };
  ImuLevelPanel.prototype.update = function (sample, connected, busy) {
    if (this.connected !== !!connected || this.busy !== !!busy) this.resetHold();
    this.sample = sample || null; this.connected = !!connected; this.busy = !!busy; this.render();
  };
  ImuLevelPanel.prototype.render = function () {
    var s = this.sample || {}, now = Date.now(), stored = savedTarget(this.target);
    if (stored !== this.target) { this.target = stored; this.select.value = String(stored); this.resetHold(); }
    var state = !this.connected ? 'disconnected' : this.busy ? 'paused' : s.status || 'waiting';
    var valid = [s.roll_deg, s.pitch_deg, s.tilt_deg].every(finite) && s.tilt_deg >= 0 && s.tilt_deg <= 180;
    var fresh = finite(s.receivedAt) && now >= s.receivedAt - 100 && now - s.receivedAt <= FRESH_MS;
    if (state === 'ok' || state === 'moving') {
      if (!valid) state = 'unavailable';
      else if (!fresh) state = 'stale';
    }
    var measurable = state === 'ok' || state === 'moving';
    if (state === 'ok' && s.tilt_deg <= this.target) {
      if (s.seq !== this.lastSeq) {
        if (this.lastGood === null || s.receivedAt - this.lastGood > 700 || s.receivedAt < this.lastGood || (finite(this.lastSeq) && s.seq < this.lastSeq)) this.first = s.receivedAt;
        this.lastGood = s.receivedAt; this.lastSeq = s.seq;
      }
      state = this.first !== null && this.lastGood - this.first >= HOLD_MS ? 'ready' : 'settling';
    } else {
      this.resetHold();
      if (state === 'ok') state = 'adjust';
    }
    var labels = {
      disconnected: ['키트 연결을 기다립니다', 'Pi를 연결하면 센서 각도를 계속 확인합니다.'],
      waiting: ['센서 값을 기다립니다', '받침을 움직이지 않은 상태로 잠시 기다려 주세요.'],
      unsupported: ['Pi 프로그램 업데이트가 필요합니다', '이 Pi 프로그램에는 IMU 수평계 기능이 없습니다. 최신 수신 프로그램을 설치해 주세요.'],
      unavailable: ['IMU를 확인할 수 없습니다', s.message || '센서의 전원·I²C 배선·주소와 Pi 설정을 확인하세요.'],
      stale: ['각도 수신이 멈췄습니다', '새 측정값이 올 때까지 수평 상태를 판단하지 않습니다. 연결과 센서를 확인하세요.'],
      paused: ['실행 중에는 수평계를 잠시 멈춥니다', '제어·점검·키트 맞추기가 끝나면 각도 표시가 다시 시작됩니다.'],
      moving: ['움직임이 감지되었습니다', '지금은 수평을 판정하지 않습니다. 조정을 멈추고 받침에서 손을 떼 주세요.'],
      adjust: ['받침을 조금 더 조정해 주세요', '앞뒤·좌우 각도가 0°에 가까워지도록 조정하세요. 전체 기울기 ' + this.target + '° 이내가 목표입니다.'],
      settling: ['목표 범위 안 · 잠시 그대로 유지하세요', '새 측정값이 2초 동안 목표 범위 안에 있는지 확인합니다.'],
      ready: ['수평 조정 목표를 충족했습니다', '전체 기울기가 ' + this.target + '° 이내로 2초 동안 유지됐습니다. 키트 점검으로 이어가세요.']
    };
    var text = labels[state] || labels.unavailable;
    this.el.dataset.state = state;
    var statusEl = this.el.querySelector('.imu-level-status');
    if (statusEl.textContent !== text[0]) statusEl.textContent = text[0];
    this.el.querySelector('.imu-level-hint').textContent = text[1];
    function signed(v) { return (v > 0 ? '+' : '') + v.toFixed(1) + '°'; }
    this.el.querySelector('.imu-angle-roll').textContent = measurable ? signed(s.roll_deg) : '—';
    this.el.querySelector('.imu-angle-pitch').textContent = measurable ? signed(s.pitch_deg) : '—';
    this.el.querySelector('.imu-angle-total').textContent = measurable ? s.tilt_deg.toFixed(1) + '°' : '—';
    this.el.querySelector('.imu-source').textContent = s.fake ? '가상 IMU · 통신 시험' : 'MPU-9250 · ' + (measurable ? '실시간' : this.connected ? '확인 중' : '대기');
    this.el.querySelector('.imu-target-ring').setAttribute('r', String(66 * this.target / 5));
    var bubble = this.el.querySelector('.imu-bubble'), x = s.roll_deg, y = -s.pitch_deg, r = Math.hypot(x, y);
    bubble.setAttribute('visibility', measurable ? 'visible' : 'hidden');
    if (measurable) { var scale = 66 / Math.max(5, r); bubble.setAttribute('cx', String(90 + x * scale)); bubble.setAttribute('cy', String(90 + y * scale)); }
    this.el.querySelector('.imu-hold-fill').style.width = (state === 'ready' ? 100 : state === 'settling' && this.first !== null ? Math.min(100, 100 * (this.lastGood - this.first) / HOLD_MS) : 0) + '%';
    this.select.disabled = this.busy;
    if (this.onState) this.onState({state:state,text:text[0],tilt:measurable ? s.tilt_deg : null,fake:!!s.fake});
  };
  ImuLevelPanel.prototype.destroy = function () { clearInterval(this.timer); };
  PS.ImuLevelPanel = ImuLevelPanel;
})(window.PS = window.PS || {});
