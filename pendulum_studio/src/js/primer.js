(function () {
  'use strict';
  const C = window.RLPrimer, $ = id => document.getElementById(id);
  const arrows = ['↑', '→', '↓', '←'];
  let world, history = [], bestEpisode = null, selected = 0, timer = null, route = [], current = -1, machine;
  // Match the main app: persistent experiment on the left, instructions on the right.
  const scene = name => document.querySelector('[data-scene="' + name + '"]');
  const gridWork = document.querySelector('#grid .workbench');
  const gridArena = document.querySelector('#grid .arena');
  const qInfo = gridArena.querySelector('.q-info'); qInfo.classList.add('card');
  gridWork.appendChild(qInfo);
  const chartCard = document.createElement('article'); chartCard.className = 'card';
  const chartTitle = document.createElement('h3'); chartTitle.textContent = '학습 기록을 읽어 봅시다'; chartCard.appendChild(chartTitle);
  const chart = $('rewardCurve'), chartNote = chart.nextElementSibling;
  chartCard.appendChild(chart); chartCard.appendChild(chartNote); chartCard.appendChild(gridArena.querySelector('details')); gridWork.appendChild(chartCard);
  scene('grid').appendChild(gridArena);
  scene('bandit').appendChild($('machines'));
  scene('future').appendChild(document.querySelector('#future .cards.two'));
  const sceneTitles = { basics: 'AI가 배우는 과정', grid: '목표까지 길찾기', bandit: '별을 주는 자판기', future: '지금 점수와 나중 점수', bridge: '회전 도립진자', modeling: '구조를 수학으로 표현하기' };
  function pause() { clearInterval(timer); timer = null; $('stopRoute').disabled = true; }
  function topic(name, focus) {
    pause();
    document.querySelectorAll('[data-topic]').forEach(b => {
      const on = b.dataset.topic === name;
      b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1;
      $(b.dataset.topic).hidden = !on;
      if (on) { if (focus) b.focus(); b.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    });
    document.querySelectorAll('[data-scene]').forEach(s => { s.hidden = s.dataset.scene !== name; });
    $('sceneTitle').textContent = sceneTitles[name];
    $('stageFooterPill').textContent = name === 'modeling' ? '모델' : '에이전트';
    $('stageFooterText').textContent = name === 'modeling' ? '구조와 물리 법칙으로 다음 움직임을 표현합니다' : '결과를 보며 더 나은 선택을 배웁니다';
    if (name === 'grid') drawEpisodePaths();
  }
  const tabs = Array.from(document.querySelectorAll('[data-topic]'));
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => topic(b.dataset.topic));
    b.addEventListener('keydown', e => {
      let n = i;
      if (e.key === 'ArrowRight') n = (i + 1) % tabs.length;
      else if (e.key === 'ArrowLeft') n = (i + tabs.length - 1) % tabs.length;
      else if (e.key === 'Home') n = 0;
      else if (e.key === 'End') n = tabs.length - 1;
      else return;
      e.preventDefault(); topic(tabs[n].dataset.topic, true);
    });
  });
  document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => { topic(b.dataset.go, true); window.scrollTo(0, 0); }));
  window.addEventListener('message', e => { if (e.source === parent && e.data && e.data.type === 'primer-pause') pause(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
  window.addEventListener('pagehide', pause);
  $('continueLesson').addEventListener('click', () => {
    if (window.parent !== window) parent.postMessage({ type: 'primer-continue' }, '*');
    else window.location.href = 'index.html?step=1';
  });
  $('sceneContinue').addEventListener('click', () => $('continueLesson').click());

  function episodeSummary(episode, number) {
    return number + '회차 · 보상 합 ' + episode.total.toFixed(1) + ' · ' + episode.steps + '걸음 · ' + episode.reason;
  }
  function updateEpisodeSummaries() {
    $('bestPathSummary').textContent = bestEpisode ? episodeSummary(bestEpisode.episode, bestEpisode.number) : '학습하면 최고 기록이 표시됩니다.';
    $('latestPathSummary').textContent = history.length ? episodeSummary(history[history.length - 1], history.length) + (bestEpisode.number === history.length ? ' (최고 기록과 같은 시도)' : '') : '학습하면 마지막 시도가 표시됩니다.';
  }
  function drawEpisodePaths() {
    const svg = $('episodePaths'), board = $('gridBoard'), bounds = board.getBoundingClientRect();
    svg.replaceChildren();
    if (!history.length || !bounds.width || !bounds.height) return;
    svg.setAttribute('viewBox', '0 0 ' + bounds.width + ' ' + bounds.height);
    const ns = 'http://www.w3.org/2000/svg';
    function draw(episode, kind, offset) {
      const points = episode.path.map(s => {
        const cell = board.children[s].getBoundingClientRect();
        return [cell.left - bounds.left + cell.width / 2 + offset, cell.top - bounds.top + cell.height / 2 + offset];
      });
      const group = document.createElementNS(ns, 'g'); group.setAttribute('class', 'episode-trace ' + kind);
      const line = document.createElementNS(ns, 'polyline');
      line.setAttribute('points', points.map(p => p.join(',')).join(' ')); group.appendChild(line);
      const end = document.createElementNS(ns, 'circle'), last = points[points.length - 1];
      end.setAttribute('cx', last[0]); end.setAttribute('cy', last[1]); end.setAttribute('r', '6'); group.appendChild(end);
      svg.appendChild(group);
    }
    if ($('showBestPath').checked && bestEpisode) draw(bestEpisode.episode, 'best-trace', -4);
    if ($('showLatestPath').checked) draw(history[history.length - 1], 'latest-trace', 4);
  }
  ['showBestPath', 'showLatestPath'].forEach(key => $(key).addEventListener('change', drawEpisodePaths));
  new ResizeObserver(drawEpisodePaths).observe($('gridBoard'));

  function drawGrid() {
    const board = $('gridBoard');
    // Keep the buttons alive so selecting a cell does not discard keyboard focus.
    if (!board.children.length) world.cells.forEach((_cell, s) => {
      const b = document.createElement('button'); b.type = 'button';
      b.addEventListener('click', () => { selected = s; drawGrid(); }); board.appendChild(b);
    });
    world.cells.forEach((cell, s) => {
      const b = board.children[s], terminal = cell === 'G' || cell === 'X' || cell === '#';
      b.className = 'cell' + (cell === '#' ? ' wall' : cell === 'X' ? ' pit' : cell === 'G' ? ' goal' : '') + (selected === s ? ' selected' : '') + (route.includes(s) && !terminal ? ' path' : '') + (current === s ? ' current' : '');
      const symbol = current === s ? '●' : cell === '#' ? '■' : cell === 'X' ? '×' : cell === 'G' ? 'G' : cell === 'S' ? 'S' : history.length ? arrows[C.best(world.q[s])] : '·';
      b.textContent = '';
      const glyph = document.createElement('span'); glyph.className = 'cell-symbol'; glyph.textContent = symbol; b.appendChild(glyph);
      if (!terminal) { const small = document.createElement('small'); small.textContent = history.length ? Math.max(...world.q[s]).toFixed(1) : '미학습'; b.appendChild(small); }
      b.setAttribute('aria-label', (Math.floor(s / 6) + 1) + '행 ' + (s % 6 + 1) + '열 ' + (cell === '#' ? '벽' : cell === 'X' ? '함정' : cell === 'G' ? '목표' : cell === 'S' ? '출발' : '빈 칸') + (current === s ? ', 현재 위치' : '') );
      b.setAttribute('aria-pressed', String(selected === s));
    });
    $('cellTitle').textContent = (Math.floor(selected / 6) + 1) + '행 ' + (selected % 6 + 1) + '열의 Q값';
    const q = world.q[selected], terminal = '#XG'.includes(world.cells[selected]);
    $('qValues').innerHTML = terminal ? '<p class="note">벽이나 종료 칸에서는 다음 행동을 배우지 않습니다.</p>' : q.map((v, i) => '<div class="q-row' + (v === Math.max(...q) ? ' best' : '') + '"><span>' + arrows[i] + '</span><span>' + v.toFixed(2) + '</span></div>').join('');
    drawEpisodePaths();
  }
  function curve() {
    const svg = $('rewardCurve');
    if (!history.length) { svg.innerHTML = '<text x="40" y="65" fill="#58677a" font-size="13">학습하면 여기에 보상 기록이 쌓입니다.</text>'; return; }
    const values = history.map(h => h.total), min = Math.min(-1, ...values), max = Math.max(1, ...values);
    const pts = values.map((v, i) => (45 + i / Math.max(1, values.length - 1) * 530).toFixed(1) + ',' + (95 - (v - min) / (max - min) * 75).toFixed(1)).join(' ');
    svg.innerHTML = '<path d="M45 12 V95 H580" fill="none" stroke="#bdcadc"/><polyline points="' + pts + '" fill="none" stroke="#315bd3" stroke-width="2"/><text x="0" y="25" font-size="11" fill="#58677a">' + max.toFixed(1) + '</text><text x="0" y="95" font-size="11" fill="#58677a">' + min.toFixed(1) + '</text><text x="45" y="115" font-size="11" fill="#58677a">1회</text><text x="525" y="115" font-size="11" fill="#58677a">' + history.length + '회</text>';
  }
  function resetGrid() {
    pause(); history = []; bestEpisode = null; route = []; current = -1;
    world = C.grid({ map: $('map').value, epsilon: +$('epsilon').value, gamma: +$('gridGamma').value, stepReward: +$('stepReward').value }); selected = world.start;
    $('epsOut').textContent = world.opts.epsilon.toFixed(2); $('gridGammaOut').textContent = world.opts.gamma.toFixed(2);
    $('episodes').textContent = '0회'; $('success').textContent = '—'; $('meanReward').textContent = '—';
    $('gridStatus').textContent = '새 조건으로 초기화했습니다. 학습 전 시험과 학습 후 시험을 비교해 보세요.';
    $('updateDetail').textContent = '학습 후 갱신 내역이 표시됩니다.'; updateEpisodeSummaries(); drawGrid(); curve();
  }
  function train(count) {
    pause(); route = []; current = -1;
    for (let i = 0; i < count; i++) {
      const episode = world.episode(true); history.push(episode);
      if (!bestEpisode || episode.total > bestEpisode.episode.total + 1e-9) bestEpisode = { episode, number: history.length };
    }
    const recent = history.slice(-20), last = history[history.length - 1], u = last.last;
    $('episodes').textContent = history.length + '회';
    $('success').textContent = Math.round(recent.filter(h => h.goal).length / recent.length * 100) + '% (' + recent.length + '회)';
    $('meanReward').textContent = (recent.reduce((s, h) => s + h.total, 0) / recent.length).toFixed(1);
    $('gridStatus').textContent = count + '회 추가 학습 완료. 마지막 시도: ' + last.reason + ', ' + last.steps + '걸음. 이제 배운 정책을 시험해 보세요.';
    $('updateDetail').textContent = (Math.floor(u.state / 6) + 1) + '행 ' + (u.state % 6 + 1) + '열에서 ' + arrows[u.action] + ' 선택 → 보상 ' + u.reward.toFixed(1) + '. Q: ' + u.old.toFixed(3) + ' → ' + u.updated.toFixed(3) + (u.terminal ? ' (종료 경험)' : '');
    updateEpisodeSummaries(); drawGrid(); curve();
  }
  ['map', 'epsilon', 'gridGamma', 'stepReward'].forEach(k => $(k).addEventListener('change', resetGrid));
  $('epsilon').addEventListener('input', () => { $('epsOut').textContent = (+$('epsilon').value).toFixed(2); });
  $('gridGamma').addEventListener('input', () => { $('gridGammaOut').textContent = (+$('gridGamma').value).toFixed(2); });
  $('gridReset').addEventListener('click', resetGrid);
  $('trainOne').addEventListener('click', () => train(1)); $('trainHundred').addEventListener('click', () => train(100));
  $('playRoute').addEventListener('click', () => {
    pause(); const result = world.episode(false); let i = 0; route = []; current = world.start;
    $('stopRoute').disabled = false; $('gridStatus').textContent = '탐험 없이 정책 시험 중 · Q표는 바뀌지 않습니다.'; drawGrid();
    timer = setInterval(() => {
      current = result.path[i]; route.push(current); drawGrid(); i++;
      if (i >= result.path.length) { pause(); $('gridStatus').textContent = '시험 결과: ' + result.reason + ' · ' + result.steps + '걸음 · 보상 합 ' + result.total.toFixed(1) + '. 학습 성공률과 별도의 시험입니다.'; }
    }, 160);
  });
  $('stopRoute').addEventListener('click', () => { pause(); $('gridStatus').textContent = '시험 재생을 멈췄습니다. 학습한 Q표는 유지됩니다.'; });

  function drawBandit() {
    if (!$('machines').children.length) ['A', 'B', 'C'].forEach((name, i) => {
      const card = document.createElement('article'); card.className = 'card machine';
      card.innerHTML = '<div class="machine-icon">' + name + '</div><h3>자판기 ' + name + '</h3><p>관측한 평균 보상</p><strong class="estimate"></strong><div class="meter"><svg viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true"><rect height="8" width="0" fill="#315bd3"/></svg></div><p class="count"></p><button>직접 선택 ' + name + '</button>';
      card.querySelector('button').addEventListener('click', () => { const r = machine.pull(i); banditMessage(r, 1, '직접 선택'); drawBandit(); }); $('machines').appendChild(card);
    });
    Array.from($('machines').children).forEach((card, i) => { card.querySelector('.estimate').textContent = machine.n[i] ? machine.q[i].toFixed(2) : '—'; card.querySelector('.count').textContent = machine.n[i] + '번 선택'; card.querySelector('rect').setAttribute('width', machine.q[i] * 100); });
  }
  function banditMessage(r, count, kind) { $('banditStatus').textContent = kind + ' ' + count + '회 · 마지막 선택 ' + 'ABC'[r.action] + ': 별 ' + r.reward + '개. 총 ' + machine.n.reduce((s, n) => s + n, 0) + '번 선택 / 별 ' + machine.total() + '개'; }
  function autoBandit(n) { let r; for (let i = 0; i < n; i++) r = machine.step(+$('banditEpsilon').value); banditMessage(r, n, 'AI 선택'); drawBandit(); }
  $('banditEpsilon').addEventListener('input', () => { $('banditEpsOut').textContent = (+$('banditEpsilon').value).toFixed(2); });
  $('banditOne').addEventListener('click', () => autoBandit(1)); $('banditHundred').addEventListener('click', () => autoBandit(100));
  $('banditReset').addEventListener('click', () => { machine = C.bandit(7); drawBandit(); $('banditStatus').textContent = '기록을 초기화했습니다. 난수 시드 7에서 다시 시작합니다.'; });
  function future() {
    const gamma = +$('futureGamma').value, value = C.discounted([0, 0, 0, 8], gamma);
    $('futureGammaOut').textContent = gamma.toFixed(2); $('futureValue').textContent = value.toFixed(2) + '점';
    $('futureStatus').textContent = '이 가중치에서는 ' + (Math.abs(value - 3) < .001 ? '두 선택의 가치가 같습니다.' : value > 3 ? '선택 B(기다리기)의 할인 누적 보상이 더 큽니다.' : '선택 A(바로 받기)의 할인 누적 보상이 더 큽니다.') + ' 선택이 바뀌는 경계는 γ ≈ 0.721입니다.';
  }
  $('futureGamma').addEventListener('input', future);
  const questions = [
    ['목표 도착은 못 하지만 보상 합이 높아졌어요. 성공인가요?', ['성공이다', '실제 목표도 확인해야 한다'], 1, '보상은 목표를 표현한 숫자입니다. 잘못 설계하면 의도와 다른 행동을 칭찬할 수 있어요.'],
    ['같은 각도라도 진자의 다음 움직임이 다를 수 있나요?', ['그렇다. 각속도도 필요하다', '아니다. 각도만 있으면 된다'], 0, '각속도를 알면 어느 방향으로 얼마나 빠르게 움직이는지 구분할 수 있습니다.'],
    ['Q=4, 보상=2, γ=0.5, 다음 최대 Q=6, α=0.5. 종료가 아니라면 새 Q는?', ['4.5', '5', '6'], 0, '목표값은 2 + 0.5×6 = 5. 새 Q는 4 + 0.5×(5−4) = 4.5입니다.']
  ];
  const answers = new Map();
  questions.forEach((q, index) => {
    const div = document.createElement('div'); div.className = 'question'; const p = document.createElement('p'); p.textContent = (index + 1) + '. ' + q[0]; div.appendChild(p);
    const feedback = document.createElement('p'); feedback.className = 'answer'; feedback.setAttribute('aria-live', 'polite');
    q[1].forEach((answer, i) => { const b = document.createElement('button'); b.textContent = answer; b.setAttribute('aria-pressed', 'false'); b.addEventListener('click', () => {
      div.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b))); answers.set(index, i === q[2]); feedback.textContent = (i === q[2] ? '맞아요. ' : '다시 생각해 보세요. ') + q[3];
      $('quizResult').textContent = Array.from(answers.values()).filter(Boolean).length + ' / 3개 이해 확인. 틀린 문제는 다시 선택할 수 있습니다.';
    }); div.appendChild(b); }); div.appendChild(feedback); $('quiz').appendChild(div);
  });
  resetGrid(); machine = C.bandit(7); drawBandit(); future();
})();
