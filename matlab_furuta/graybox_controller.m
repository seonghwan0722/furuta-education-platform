function controller = graybox_controller(net,design,has)
% 현재 측정 상태와 직전 명령에서 이산 모델을 선형화한다.
% 아핀 항을 포함한 국소 모델로 N단계 QP를 한 번 푼다.
p = furuta_params; previous = 0;
N = design.N;
W = blkdiag(kron(eye(N-1),design.Q),design.P);
opts = [];
if has.optim
    opts = optimoptions('quadprog','Display','off');
end
controller = struct('name',"PINN-MPC",'fun',@move);
    function u = move(x,t)
        if t == 0
            previous = 0;
        end
        x(2) = wrap_theta(x(2));
        z = model(x,previous);
        A = zeros(4); h = 1e-4;
        for k = 1:4
            d = zeros(4,1); d(k) = h;
            A(:,k) = (model(x+d,previous)-model(x-d,previous))/(2*h);
        end
        lo = max(-1,previous-h); hi = min(1,previous+h);
        B = (model(x,hi)-model(x,lo))/(hi-lo);
        offset = z-A*x-B*previous;
        [F,G] = mpc_prediction(A,B,N);
        drift = zeros(4*N,1); state = zeros(4,1);
        for k = 1:N
            state = A*state+offset;
            drift(4*(k-1)+(1:4)) = state;
        end
        H = 2*(G'*W*G+design.R*eye(N));
        U = mpc_box((H+H')/2,2*G'*W*(F*x+drift),opts);
        u = U(1); previous = u;
    end
    function y = model(x,u)
        y = furuta_step(x,u,p,0,@correction);
    end
    function a = correction(x,u)
        a = double(extractdata(gray_correction(net,x,u)));
    end
end
