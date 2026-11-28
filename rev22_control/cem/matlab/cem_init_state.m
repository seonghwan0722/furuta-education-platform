function st = cem_init_state(g, seed)
% Controller memory. seed: RNG seed (cem.py uses seed + 7919*j for environment j, 0 -> 1).
s = mod(seed, 4294967296); if s == 0, s = 1; end
st = struct('xh', zeros(4,1), 'c1', 0, 'c2', 0, 'bal', false, 'home', 0, 'init', false, ...
            'mean', zeros(1, g.H/g.hold), 'rs', uint32(s), 'k', 0, 'dh', 0);
end
