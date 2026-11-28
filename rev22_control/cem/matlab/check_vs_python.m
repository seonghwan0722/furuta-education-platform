% Cross-check: MATLAB/Octave CEM controller + sp_env2-style sim against the Python reference (export_ref.py).
% Same start [0.3; 170 deg; 0.2; -0.5], design ident09, truth hw1123, xorshift RNG seed 12345.
g = cem_config(); pd = cem_rev22_plant("ident09"); pt = cem_rev22_plant("hw1123");
D = cem_design(pd, [3 10 5 5], [50 200], 0.01, g.dob);
x0 = [0.3; deg2rad(170); 0.2; -0.5];
cases = {'nom', struct('T', 6, 'frac', 0, 'stic', 0, 'coulTh', 0, 'biasDeg', 0, 'regen', []); ...
         'hw',  struct('T', 6, 'frac', 1, 'stic', 0.5, 'coulTh', 1e-3, 'biasDeg', -1, 'regen', [])};
for c = 1:size(cases,1)
    ev = cases{c,2}; tic; [X, A] = cem_sim(D, g, x0, pt, ev, 12345); t = toc;
    up = load(['ref_' cases{c,1} '_u.csv']); xp = csvread(['ref_' cases{c,1} '_x.csv'])';
    n = numel(up); same = find(abs(A(1:n)' - up) > 1e-9, 1); if isempty(same), same = n + 1; end
    m = cem_metrics(X, A);
    printf('%s: %.1f s sim, %.1f ms/step | identical u for first %d of %d steps | max|du| %.3g | max|dx| %.3g | passed %d reach %.2f s\n', ...
        cases{c,1}, t, 1000*t/n, same - 1, n, max(abs(A(1:n)' - up)), max(abs(X(:) - xp(:))), m.passed, m.reach);
end
