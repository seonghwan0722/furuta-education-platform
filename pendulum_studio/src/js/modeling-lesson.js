/* Geometry-only teaching view. Does not step the plant, train a policy or send commands. */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const C = window.PS && window.PS.MODEL;
  const rad = Math.PI / 180;
  const point = (cx, cy, r, a) => [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  const setPoint = (id, p) => { $(id).setAttribute('cx', p[0]); $(id).setAttribute('cy', p[1]); };
  const degreeText = value => (Math.abs(value) < .00001 ? '0' : value.toFixed(0).replace('-', '−')) + '°';

  // Angles are in radians here. SVG y points down, unlike the mechanical z axis.
  function arc(cx, cy, radius, start, end) {
    if (Math.abs(end - start) < 1e-8) return '';
    const a = point(cx, cy, radius, start), b = point(cx, cy, radius, end);
    return 'M' + a.join(' ') + ' A' + radius + ' ' + radius + ' 0 0 ' + (end > start ? 0 : 1) + ' ' + b.join(' ');
  }
  function render() {
    const thetaDeg = Number($('modelTheta').value), alphaDeg = Number($('modelAlpha').value);
    const theta = thetaDeg * rad, alpha = alphaDeg * rad;
    const phiDeg = ((alphaDeg - 180 + 180) % 360 + 360) % 360 - 180;
    const heightRatio = 1 - Math.cos(alpha);
    const tip = point(110, 165, 80, theta);
    $('modelArm').setAttribute('d', 'M110 165L' + tip.join(' '));
    setPoint('modelHinge', tip);
    $('modelThetaArc').setAttribute('d', arc(110, 165, 29, 0, theta));
    const armLabel = point(110, 165, 43, theta);
    $('modelArmLabel').setAttribute('x', armLabel[0]); $('modelArmLabel').setAttribute('y', armLabel[1] - 10);

    const tipPend = [330 + 100 * Math.sin(alpha), 172 + 100 * Math.cos(alpha)];
    const com = [330 + 50 * Math.sin(alpha), 172 + 50 * Math.cos(alpha)];
    $('modelRod').setAttribute('d', 'M330 172L' + tipPend.join(' '));
    setPoint('modelCOM', com);
    // The pedagogical COM is halfway along a uniform rod, not a measured rev11 COM.
    const right = com[0] >= 330;
    $('modelCOMLabel').setAttribute('x', com[0] + (right ? -12 : 12));
    $('modelCOMLabel').setAttribute('y', com[1] - 12);
    $('modelCOMLabel').setAttribute('text-anchor', right ? 'end' : 'start');
    $('modelAlphaArc').setAttribute('d', arc(330, 172, 30, -Math.PI / 2, alpha - Math.PI / 2));

    $('modelThetaValue').textContent = $('modelThetaOut').textContent = degreeText(thetaDeg);
    $('modelAlphaValue').textContent = $('modelAlphaOut').textContent = degreeText(alphaDeg);
    $('modelPhiValue').textContent = degreeText(phiDeg);
    $('modelHeightValue').textContent = heightRatio.toFixed(3);
    $('modelDrawingDesc').textContent = '팔 각도 ' + thetaDeg + '도, 진자 각도 ' + alphaDeg + '도. 직립 오차 ' + phiDeg + '도. 아래 기준 상대 높이는 무게중심 거리의 ' + heightRatio.toFixed(3) + '배입니다. 주황색 점은 설명용 균일 막대의 무게중심입니다.';
    document.querySelectorAll('[data-model-angle]').forEach(button => {
      const a = Number(button.dataset.modelAngle);
      button.setAttribute('aria-pressed', String(a === alphaDeg || (a === 180 && alphaDeg === -180)));
    });
  }
  ['modelTheta', 'modelAlpha'].forEach(id => $(id).addEventListener('input', render));
  document.querySelectorAll('[data-model-angle]').forEach(button => button.addEventListener('click', () => {
    $('modelAlpha').value = button.dataset.modelAngle; render();
  }));
  document.querySelectorAll('[data-model-answer]').forEach(button => button.addEventListener('click', () => {
    const correct = button.dataset.modelAnswer === 'coupling';
    $('modelCheckFeedback').textContent = correct
      ? '맞아요. 두 축의 움직임은 질량행렬 M과 속도 항 h를 통해 연결됩니다. 진자 축 입력이 0이어도 팔의 움직임과 중력이 진자를 움직입니다.'
      : '진자 축에는 직접 구동하는 모터가 없습니다. [τ, 0]의 0을 확인해 보세요. 팔과의 결합과 중력 때문에 진자가 움직입니다.';
    document.querySelectorAll('[data-model-answer]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  }));
  if (C) {
    $('modelRuntime').textContent = C.name + ' · 물리 계산 ' + (C.timestep * 1000).toFixed(0) + ' ms · 제어 ' + C.ctrl_hz + ' Hz (' + (1000 / C.ctrl_hz).toFixed(0) + ' ms)';
    $('modelObservation').textContent = '[cos θ, sin θ, cos α, sin α, θ̇ / ' + C.obs_scale.arm + ', α̇ / ' + C.obs_scale.pend + ']';
  } else {
    $('modelRuntime').textContent = '모델 설정을 읽지 못했습니다. 설명용 도식은 계속 사용할 수 있습니다.';
  }
  render();
})();
