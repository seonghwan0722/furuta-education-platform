function U = mpc_box(H,f,opts)
% 제약 QP가 불가하면 무제약 해를 포화한다.
if ~isempty(opts)
    [U,~,flag] = quadprog(H,f,[],[],[],[],-ones(size(f)),ones(size(f)),[],opts);
    if flag > 0 && all(isfinite(U))
        return
    end
end
U = max(-1,min(1,-(H\f)));
end
