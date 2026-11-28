/* Small, reproducible teaching environments. No device or hardware APIs. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RLPrimer = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function rng(seed) { let a = seed >>> 0; const next = function () { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; next.state=()=>a>>>0; next.restore=v=>{a=v>>>0;}; return next; }
  function best(values, random) { const m = Math.max(...values), ties = values.map((v, i) => v === m ? i : -1).filter(i => i >= 0); return ties[Math.floor((random || (() => 0))() * ties.length)]; }
  const maps = {
    maze: ['S.....', '.##.#.', '....#.', '.#X...', '.#.#X.', '.....G'],
    risk: ['S..X.G', '.X.X..', '...X..', '.X....', '...X..', '......']
  };
  const moves = [[-1, 0], [0, 1], [1, 0], [0, -1]];
  function qUpdate(old, reward, nextMax, alpha, gamma, terminal) { return old + alpha * (reward + (terminal ? 0 : gamma * nextMax) - old); }
  function grid(options) {
    const opts = Object.assign({ map: 'maze', seed: 7, epsilon: .25, alpha: .3, gamma: .95, stepReward: -.2 }, options);
    const rows = maps[opts.map]; if (!rows) throw Error('Unknown map');
    const cells = rows.join('').split(''), q = cells.map(() => [0, 0, 0, 0]);
    const random = rng(opts.seed), start = cells.indexOf('S');
    function transition(s, a) {
      const r = Math.floor(s / 6) + moves[a][0], c = s % 6 + moves[a][1];
      let next = r < 0 || c < 0 || r >= 6 || c >= 6 ? s : r * 6 + c;
      if (cells[next] === '#') next = s;
      const goal = cells[next] === 'G', pit = cells[next] === 'X';
      return { next, reward: goal ? 10 : pit ? -5 : opts.stepReward, terminal: goal || pit, goal };
    }
    function episode(learn) {
      let s = start, total = 0, goal = false; const path = [s]; let last;
      for (let step = 0; step < 80; step++) {
        const a = learn && random() < opts.epsilon ? Math.floor(random() * 4) : best(q[s], learn ? random : undefined);
        const t = transition(s, a), old = q[s][a], terminal = t.terminal || step === 79;
        if (learn) q[s][a] = qUpdate(old, t.reward, Math.max(...q[t.next]), opts.alpha, opts.gamma, terminal);
        last = { state: s, action: a, reward: t.reward, next: t.next, old, updated: q[s][a], terminal };
        total += t.reward; s = t.next; path.push(s); goal = t.goal;
        if (terminal) break;
      }
      return { path, total, goal, steps: path.length - 1, last, reason: goal ? '목표 도착' : cells[s] === 'X' ? '함정에 도착' : '80걸음 시간 제한' };
    }
    return { opts, cells, q, start, transition, episode, snapshot:()=>({opts:Object.assign({},opts),q:q.map(r=>r.slice()),rng:random.state()}), restore:s=>{s.q.forEach((r,i)=>q[i].splice(0,4,...r));random.restore(s.rng);} };
  }
  function bandit(seed) {
    const random = rng(seed || 7), probabilities = [.25, .5, .75], n = [0, 0, 0], q = [0, 0, 0]; let total = 0;
    function pull(a) { const reward = random() < probabilities[a] ? 1 : 0; n[a]++; q[a] += (reward - q[a]) / n[a]; total += reward; return { action: a, reward, total }; }
    function step(epsilon) { return pull(random() < epsilon ? Math.floor(random() * 3) : best(q, random)); }
    return { n, q, probabilities, pull, step, total: () => total, snapshot:()=>({n:n.slice(),q:q.slice(),total,rng:random.state()}), restore:s=>{n.splice(0,3,...s.n);q.splice(0,3,...s.q);total=s.total;random.restore(s.rng);} };
  }
  function discounted(rewards, gamma) { return rewards.reduce((sum, r, t) => sum + Math.pow(gamma, t) * r, 0); }
  return { rng, best, grid, bandit, discounted, qUpdate, maps };
});
