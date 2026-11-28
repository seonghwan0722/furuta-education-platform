% rev22 CEM-MPC evaluation in MATLAB (standalone: no lm_* / sp_* files needed).
% Same conditions as rev22_control LMPC rev22b (vx.py) and the Python CEM run (cem/vx_cem.py):
%   design model ident09, truth "hw1123" (nominal) or "ident08" (pessimistic), 10/15/20 ms, plant +/- variations,
%   hardware-like (arm stiction +50 %, pendulum zero error +/-1 deg, pendulum Coulomb 1e-3 N m), +/-1.5 A, regen budget row.
% Starts: Python seeds (starts.csv written by cem/export_starts.py) so both languages run the same 123/43 starts.
% Runtime: ~0.1-0.3 s per 10 ms step in MATLAB with rngMode "xorshift"; use QUICK = true (16 starts) or parfor.
% Set g.rngMode = "matlab" for speed (results then differ from Python sample by sample but not statistically).
here = fileparts(mfilename('fullpath')); addpath(here);
if ~exist('QUICK','var'), QUICK = true; end
if ~exist('TRUTH','var'), TRUTH = "hw1123"; end
if ~exist('TEP','var'), TEP = 25; end   % episode length [s]
g = cem_config(); pd = cem_rev22_plant("ident09"); p0 = cem_rev22_plant(TRUTH);
D = cem_design(pd, [3 10 5 5], [50 200], 0.01, g.dob);
S = csvread(fullfile(here, 'starts123.csv'))'; S43 = csvread(fullfile(here, 'starts43.csv'))';
if QUICK, nq = 16; if ~islogical(QUICK) && QUICK > 1, nq = QUICK; end; S = S(:, 1:nq); S43 = S43(:, 1:nq); end
ev0 = struct('T', TEP, 'frac', 0, 'stic', 0, 'coulTh', 0, 'biasDeg', 0, 'regen', []);
var = @(p, f, s) setfield(p, f, p.(f)*s);
C = {};
C(end+1,:) = {'d10', p0, ev0, S}; e = ev0; e.frac = 0.5; C(end+1,:) = {'d15', p0, e, S}; e = ev0; e.frac = 1; C(end+1,:) = {'d20', p0, e, S};
pv = {'gam08', 'gam', 0.8; 'gam12', 'gam', 1.2; 'coul05', 'coulomb', 0.5; 'coul125', 'coulomb', 1.25; 'alpha085', 'alpha', 0.85; 'alpha115', 'alpha', 1.15};
for i = 1:size(pv,1)
    pp = var(p0, pv{i,2}, pv{i,3}); C(end+1,:) = {pv{i,1}, pp, ev0, S43}; e = ev0; e.frac = 1; C(end+1,:) = {[pv{i,1} '_d20'], pp, e, S43};
end
e = ev0; e.stic = 0.5; e.coulTh = 1e-3; e.biasDeg = 1; C(end+1,:) = {'hwlike', p0, e, S43};
e.frac = 1; e.biasDeg = -1; C(end+1,:) = {'hwlike_d20', p0, e, S43};
e = ev0; e.frac = 1; e.regen = 0.8; C(end+1,:) = {'d20_regen08', p0, e, S};
for c = 1:size(C,1)
    X0 = C{c,4}; n = size(X0,2); R = struct('passed', {}, 'reach', {}, 'peak_arm', {}, 'peak_pend', {}, 'sat', {}, 'regenJ', {}, 'hold10', {});
    for j = 1:n       % parfor works too (each start is independent; seed 12345 + 7919*(j-1) as in cem.py)
        [X, A] = cem_sim(D, g, X0(:,j), C{c,2}, C{c,3}, mod(12345 + 7919*(j-1), 4294967296));
        R(j) = cem_metrics(X, A);
    end
    ok = [R.passed];
    fprintf('%-12s %3d/%3d  reach %.2f s  sat %.1f%%  arm %.1f  pend %.1f rad/s  max brake %.2f J\n', C{c,1}, nnz(ok), n, ...
        mean([R(ok).reach]), mean([R.sat]), max([R.peak_arm]), max([R.peak_pend]), max([R.regenJ]));
end
