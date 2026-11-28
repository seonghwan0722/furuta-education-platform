/* Illustrations only: these fixed examples never invoke the plant or change experiment settings. */
(function (PS) {
  'use strict';
  const label = '<div class="explainer-label"><span class="pill state">직접 살펴보기</span><span>설명용 예시 · 실제 실험 결과와 별개</span></div>';
  const fixed = n => (Math.abs(n) < 1e-9 ? '0.00' : n.toFixed(2).replace('-', '−'));
  const sign = n => (n > 0 ? '+' : '') + fixed(n);

  function pid(host) {
    host.innerHTML = label + `
      <h4>현재 오차가 같아도, 같은 힘이 필요할까요?</h4>
      <p>세 예시의 마지막 오차는 모두 +1°입니다. 과거에 지나온 길을 바꿔 보세요. 여기서 e는 <b>현재 기울기 − 직립 목표</b>입니다.</p>
      <div class="explainer-choices" role="group" aria-label="PID 오차 변화 예시">
        <button data-pid-case="approaching" aria-pressed="true">직립으로 돌아오는 중</button>
        <button data-pid-case="leaving" aria-pressed="false">더 기울어지는 중</button>
        <button data-pid-case="offset" aria-pressed="false">기울어진 채 유지</button>
      </div>
      <div class="explainer-plot-wrap" tabindex="0" role="region" aria-label="PID 설명 그림 · 좁은 화면에서는 좌우로 스크롤"><svg class="explainer-plot" data-pid-plot viewBox="0 0 640 250" role="img" aria-label="가상 오차의 현재값, 누적 면적과 변화율"></svg></div>
      <div class="explainer-keys"><span><i class="key-current"></i>P가 보는 현재값</span><span><i class="key-area"></i>I가 보는 부호 있는 면적</span><span><i class="key-slope"></i>D가 보는 마지막 기울기</span></div>
      <div class="explainer-values"><div><span>현재 e</span><b data-pid-current></b></div><div><span>0~4초의 ∫e dt</span><b data-pid-integral></b></div><div><span>마지막 구간 Δe/Δt</span><b data-pid-rate></b></div></div>
      <p class="explainer-feedback" data-pid-feedback aria-live="polite"></p>
      <p class="explainer-footnote">점 사이는 직선이며 초기 누적값은 0으로 둔 예입니다. 이 숫자는 P·I·D가 참고하는 신호입니다. 실제 모터 명령은 게인·부호·팔 피드백·출력 상한까지 적용해서 정합니다. 실제 앱은 rad 단위를 사용합니다.</p>`;
    const cases = {
      approaching: { e: [3, 2.5, 2, 1.5, 1], text: '현재는 +1°이지만 오차가 줄고 있어요. 변화율은 음수입니다. 누적 면적은 과거의 큰 오차를 기억합니다.' },
      leaving: { e: [0, .25, .5, .75, 1], text: '현재값은 같지만 오차가 커지고 있어요. 변화율은 양수입니다. P만 보면 같고, I·D가 보는 정보는 다릅니다.' },
      offset: { e: [1, 1, 1, 1, 1], text: '오차가 계속 남아 있지만 변하지 않으므로 변화율은 0입니다. 그동안의 오차는 누적 면적에 남습니다.' }
    };
    function render(name) {
      const data = cases[name], e = data.e;
      const x = i => 58 + i * 130, y = v => 200 - v * 48;
      const pts = e.map((v, i) => x(i) + ',' + y(v));
      const area = e.slice(1).reduce((sum, v, i) => sum + (e[i] + v) / 2, 0);
      const slope = e[4] - e[3];
      host.querySelector('[data-pid-plot]').innerHTML = `
        <path d="M58 30V200H602" fill="none" stroke="#8FA2AB"/>
        <path d="M58 152H602M58 104H602M58 56H602" stroke="#D7DEE3" stroke-dasharray="4 4"/>
        <text x="8" y="22">e (°)</text><text x="35" y="205">0</text><text x="35" y="157">1</text><text x="35" y="109">2</text><text x="35" y="61">3</text>
        <polygon points="58,200 ${pts.join(' ')} 578,200" fill="#D8E6BC" opacity=".8"/>
        <polyline points="${pts.join(' ')}" fill="none" stroke="#51606E" stroke-width="3"/>
        <path d="M${x(3)} ${y(e[3])}L${x(4)} ${y(e[4])}" stroke="#C2410C" stroke-width="5" stroke-dasharray="7 4"/>
        <path d="M578 200V${y(e[4])}" stroke="#3b6de4" stroke-dasharray="4 4"/>
        <circle cx="578" cy="${y(e[4])}" r="7" fill="#3b6de4" stroke="#fff" stroke-width="2"/>
        <text x="58" y="227">0초</text><text x="318" y="227" text-anchor="middle">2초</text><text x="578" y="227" text-anchor="middle">4초 · 지금</text>`;
      host.querySelector('[data-pid-current]').textContent = '+1.00°';
      host.querySelector('[data-pid-integral]').textContent = fixed(area) + ' °·s';
      host.querySelector('[data-pid-rate]').textContent = sign(slope) + ' °/s';
      host.querySelector('[data-pid-feedback]').textContent = data.text;
      host.querySelectorAll('[data-pid-case]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pidCase === name)));
    }
    host.querySelectorAll('[data-pid-case]').forEach(b => b.addEventListener('click', () => render(b.dataset.pidCase)));
    render('approaching');
  }

  function lqr(host) {
    host.innerHTML = label + `
      <h4>같은 두 기록도, 중요도가 바뀌면 평가가 달라져요</h4>
      <p>가상의 후보 A는 기울기 오차가 작고 힘을 많이 씁니다. B는 오차가 더 크지만 힘을 덜 씁니다. <b>기울기 제곱 합 E와 입력 제곱 합 U를 고정</b>하고 비용만 계산해 봅시다.</p>
      <div class="cost-candidates"><div><b>후보 A</b><span>E = 2 · U = 8</span></div><div><b>후보 B</b><span>E = 8 · U = 2</span></div></div>
      <div class="explainer-inputs">
        <label>기울기 중요도 qφ <output data-cost-q-out>4</output><input data-cost-q type="range" min="1" max="8" step="1" value="4" aria-label="설명용 기울기 중요도"></label>
        <label>힘 사용 중요도 R <output data-cost-r-out>1</output><input data-cost-r type="range" min="1" max="8" step="1" value="1" aria-label="설명용 힘 사용 중요도"></label>
      </div>
      <div class="explainer-plot-wrap" tabindex="0" role="region" aria-label="LQR 비용 그림 · 좁은 화면에서는 좌우로 스크롤"><svg class="explainer-plot cost-plot" data-cost-plot viewBox="0 0 640 168" role="img" aria-label="두 가상 후보의 기울기 비용과 입력 비용 비교"></svg></div>
      <div class="explainer-keys"><span><i class="key-current"></i>qφ × E</span><span><i class="key-slope"></i>R × U</span><span><i class="key-other"></i>그 밖의 상태 비용 1</span></div>
      <p class="explainer-feedback" data-cost-feedback aria-live="polite"></p>
      <p class="explainer-footnote">J = qφE + RU + 1. 다른 상태 비용은 두 후보 모두 1로 둔 설명용 계산입니다. 두 후보가 실제 진자 동역학을 만족한다는 뜻은 아닙니다. 실제 LQR은 후보 두 개 중 고르는 대신 모델과 비용으로 K를 계산합니다. 위 슬라이더는 실험 설정을 바꾸지 않습니다.</p>`;
    function render() {
      const q = +host.querySelector('[data-cost-q]').value, r = +host.querySelector('[data-cost-r]').value;
      const ja = 2 * q + 8 * r + 1, jb = 8 * q + 2 * r + 1;
      host.querySelector('[data-cost-q-out]').textContent = q;
      host.querySelector('[data-cost-r-out]').textContent = r;
      const row = (name, E, U, top) => {
        const a = q * E, b = r * U, total = a + b + 1;
        return `<text x="14" y="${top + 24}">${name}</text><rect x="86" y="${top}" width="${a * 5.5}" height="34" fill="#3b6de4"/><rect x="${86 + a * 5.5}" y="${top}" width="${b * 5.5}" height="34" fill="#C2410C"/><rect x="${86 + (a + b) * 5.5}" y="${top}" width="5.5" height="34" fill="#8FA2AB"/><text x="${100 + total * 5.5}" y="${top + 24}" class="cost-total">${total}</text><text x="86" y="${top + 57}">${a} + ${b} + 1 = ${total}</text>`;
      };
      host.querySelector('[data-cost-plot]').innerHTML = row('후보 A', 2, 8, 14) + row('후보 B', 8, 2, 94);
      host.querySelector('[data-cost-feedback]').textContent = ja === jb
        ? '두 후보의 비용이 ' + ja + '로 같습니다. 비용 기준에 따라 이 둘을 구별하지 못하는 경우도 있어요.'
        : '이 두 가상 후보 중 비용이 작은 것은 ' + (ja < jb ? 'A' : 'B') + '입니다. A: ' + ja + ', B: ' + jb + '. 실제 LQR의 최적해를 계산한 결과는 아닙니다.';
    }
    host.querySelectorAll('input').forEach(input => input.addEventListener('input', render));
    render();
  }

  function lmpc(host) {
    host.innerHTML = label + `
      <h4>계획은 여러 칸, 적용은 첫 한 칸</h4>
      <p>아래는 5칸짜리 가상의 입력 계획입니다. 다음 주기로 넘어가면 <b>새로 측정한 상태</b>에서 계획을 다시 세워요.</p>
      <div class="mpc-cycle"><span class="pill state" data-mpc-time></span><span>→ 새 계획 계산 → 첫 명령만 적용</span></div>
      <div class="explainer-plot-wrap" tabindex="0" role="region" aria-label="LMPC 계획 그림 · 좁은 화면에서는 좌우로 스크롤"><svg class="explainer-plot" data-mpc-plot viewBox="0 0 640 250" role="img" aria-label="첫 명령과 이후 계획을 구분한 다섯 칸의 모터 명령"></svg></div>
      <div class="explainer-keys"><span><i class="key-current"></i>지금 적용할 첫 명령</span><span><i class="key-other"></i>아직 실행하지 않은 계획</span></div>
      <div class="mpc-command"><span>이번에 적용하는 명령</span><b data-mpc-first></b></div>
      <div class="explainer-choices"><button class="primary" data-mpc-next>한 주기 뒤 · 다시 계획하기 →</button><button data-mpc-reset>처음부터 보기</button></div>
      <p class="explainer-feedback" data-mpc-feedback aria-live="polite"></p>
      <p class="explainer-footnote">수치는 재계획의 뜻을 보여주기 위해 정한 예시입니다. 선형 모델·QP·진자 시뮬레이션을 계산한 결과가 아닙니다. 그림의 상한 ±0.8과 5칸은 이 설명에서만 사용하며 실험 설정의 상한·N을 바꾸지 않습니다.</p>`;
    const plans = [[.6, .4, .2, .1, 0], [.45, .25, .05, -.05, 0], [.25, .1, -.05, 0, 0]];
    let k = 0;
    function render() {
      const plan = plans[k], zero = 132, scale = 98;
      host.querySelector('[data-mpc-time]').textContent = '측정 시점 k = ' + k;
      host.querySelector('[data-mpc-first]').textContent = 'u[' + k + '] = ' + sign(plan[0]);
      let markup = `<text x="10" y="24">정규화 명령 u</text><path d="M54 ${zero}H616" stroke="#8FA2AB"/><path d="M54 ${zero - .8 * scale}H616M54 ${zero + .8 * scale}H616" stroke="#C2410C" stroke-dasharray="6 5"/><text x="7" y="${zero - .8 * scale + 5}">+0.8</text><text x="15" y="${zero + 5}">0</text><text x="7" y="${zero + .8 * scale + 5}">−0.8</text>`;
      plan.forEach((u, i) => {
        const x = 84 + i * 108, top = zero - Math.max(0, u) * scale, height = Math.max(2, Math.abs(u) * scale);
        markup += `<rect x="${x}" y="${top}" width="58" height="${height}" rx="3" fill="${i ? '#dde5ee' : '#3b6de4'}" stroke="${i ? '#8FA2AB' : '#3b6de4'}" ${i ? 'stroke-dasharray="4 3"' : ''}/><text x="${x + 29}" y="${top - 10}" text-anchor="middle">${sign(u)}</text><text x="${x + 29}" y="237" text-anchor="middle">u[${k + i}]</text>`;
      });
      host.querySelector('[data-mpc-plot]').innerHTML = markup;
      const feedback = host.querySelector('[data-mpc-feedback]');
      if (k === 0) {
        feedback.textContent = '지금은 +0.60 한 개만 적용합니다. +0.40, +0.20 같은 뒤의 명령은 아직 계획일 뿐입니다. 다음 시점에 그대로 쓰는지 확인해 보세요.';
      } else if (plan[0] === plans[k - 1][1]) {
        feedback.textContent = '이번 u[' + k + ']는 이전 계획과 새 계획 모두 ' + sign(plan[0]) + '입니다. 다시 계획해도 같은 명령이 나올 수 있어요. 중요한 것은 이전 계획을 그대로 재생하는 대신 새 상태에서 다시 결정한다는 점입니다.';
      } else {
        feedback.textContent = '이전 계획에서는 u[' + k + '] = ' + sign(plans[k - 1][1]) + '였지만, 이 예시의 새 계획에서는 ' + sign(plan[0]) + '입니다. 새 관측을 바탕으로 다시 정하며 나머지 명령은 아직 실행하지 않습니다.';
      }
      host.querySelector('[data-mpc-next]').disabled = k === plans.length - 1;
    }
    host.querySelector('[data-mpc-next]').addEventListener('click', () => { if (k < plans.length - 1) { k++; render(); } });
    host.querySelector('[data-mpc-reset]').addEventListener('click', () => { k = 0; render(); });
    render();
  }
  PS.ControlExplainers = { mount(method, host) {
    if (!host) return;
    host.classList.add('control-explainer');
    const draw = { pid, lqr, lmpc }[method];
    if (draw) draw(host);
  } };
})(window.PS = window.PS || {});
