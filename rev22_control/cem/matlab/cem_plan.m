function [u0, mean, rs, Jbest] = cem_plan(x, home, mean, uprev, bal, rs, p, g, P, dh)
% One Cross-Entropy-Method solve. mean (1 x M) = warm-start knot sequence, rs = uint32 RNG state.
% Sample 1 is the current mean, samples 2..K are mean + std.*N(0,1) clipped to [-1,1];
% the nelite cheapest set the new mean (smoothed) and std (floored at stdmin), repeated g.iters times.
M = numel(mean); K = g.K; ne = g.nelite;
if bal, sd = g.std0Bal*ones(1,M); smin = g.stdminBal; else, sd = g.std0*ones(1,M); smin = g.stdmin; end
U = zeros(K, M);
for it = 1:g.iters
    U(1,:) = mean;
    for k = 2:K
        if g.rngMode == "xorshift", [nz, rs] = cem_randn(rs, M); else, nz = randn(M, 1); end
        U(k,:) = min(1, max(-1, mean + sd.*nz'));
    end
    J = cem_rollout_cost(x, home, U, uprev, bal, p, g, P, dh);
    [~, idx] = sort(J);                 % MATLAB sort is stable (= mergesort in cem.py)
    E = U(idx(1:ne), :);
    m = sum(E, 1)/ne;
    s = sqrt(sum((E - m).^2, 1)/ne);
    mean = g.smooth*mean + (1 - g.smooth)*m;
    sd = max(s, smin);
end
u0 = mean(1); Jbest = J(idx(1));
end
