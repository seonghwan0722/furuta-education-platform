function [K,P] = riccati_gain(A,B,Q,R,hasControl)
% 도구 상자가 없으면 이산 리카티 고정점 반복을 사용한다.
if hasControl
    [K,P] = dlqr(A,B,Q,R);
    return
end
P = Q;
for i = 1:20000
    K = (R+B'*P*B)\(B'*P*A);
    next = Q+A'*P*(A-B*K);
    next = (next+next')/2;
    if norm(next-P,'fro')<1e-11*max(1,norm(P,'fro'))
        P = next;
        K = (R+B'*P*B)\(B'*P*A);
        assert(max(abs(eig(A-B*K)))<1,'리카티 해가 안정화하지 못했습니다.');
        return
    end
    P = next;
end
error('이산 리카티 반복이 수렴하지 않았습니다.');
end
