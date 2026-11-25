function [controllers,design] = design_classical(has,tunePID)
% 공칭 모델로만 제어기를 설계한다.
arguments
    has = check_toolboxes
    tunePID = true
end
p = furuta_params;
[~,~,A,B] = furuta_linearize(p);
Q = diag([10 10 1 1]); R = 1; N = 20;
s = furuta_scenarios;
for i = 1:10
    [K,P] = riccati_gain(A,B,Q,R,has.control);
    r = run_scenario(@(x,t) -K*x,s(1));
    if r.metrics.SaturationRatio<=.05 && isfinite(r.metrics.Settle_s)
        break
    end
    if i < 10
        R = R*2;
    end
end
fprintf('LQR R = %.4g, K 및 이산 폐루프 극점\n',R);
disp(K)
disp(eig(A-B*K))
g0 = [7.3 .69 .56 .30 .05];
g = g0;
if tunePID
    z = fminsearch(@objective,zeros(1,5),optimset('MaxFunEvals',150,'Display','off'));
    g = g0.*exp(max(-3,min(3,z)));
end
fprintf('PID 이득 [P D 팔P 팔D I]\n');
disp(g)
[pid,pidReset] = pid_controller(g,p.Ts);
[lmpc,backend] = make_lmpc(A,B,Q,R,P,N,p.Ts,has);
fprintf('LMPC 구현 %s\n',backend);
controllers = struct('name',{"PID","LQR","LMPC"},'fun',{ ...
    swing_controller(pid,pidReset), ...
    swing_controller(@(x,t) -K*x,[],[deg2rad(13) .2]),swing_controller(lmpc,[])});
design = struct('A',A,'B',B,'Q',Q,'R',R,'P',P,'K',K,'N',N,'pidGains',g,'backend',backend);
save(fullfile(results_dir,'classical.mat'),'design')
    function value = objective(z)
        fn = pid_controller(g0.*exp(max(-3,min(3,z))),p.Ts);
        out = run_scenario(fn,s(1));
        value = out.metrics.ITAE+.1*out.metrics.ISCI;
        if ~isfinite(value)
            value = 1e6;
        end
    end
end

function [fn,reset] = pid_controller(g,dt)
% 조건부 적분으로 포화 방향의 누적을 막는다.
integral = 0;
fn = @control;
reset = @reset_integral;
    function reset_integral
        integral = 0;
    end
    function u = control(x,t)
        if t == 0
            reset_integral
        end
        e = wrap_theta(x(2));
        base = g(1)*e+g(2)*x(4)+g(3)*x(1)+g(4)*x(3);
        candidate = base+g(5)*(integral+dt*e);
        if abs(candidate)<=1 || sign(candidate)~=sign(e)
            integral = integral+dt*e;
        end
        u = max(-1,min(1,base+g(5)*integral));
    end
end

function [fn,backend] = make_lmpc(A,B,Q,R,P,N,Ts,has)
opts = [];
if has.optim
    opts = optimoptions('quadprog','Display','off');
end
[F,G] = mpc_prediction(A,B,N);
W = blkdiag(kron(eye(N-1),Q),P);
H = 2*(G'*W*G+R*eye(N));
M = 2*G'*W*F;
backend = "포화 무제약 MPC";
if has.optim
    backend = "quadprog";
end
fn = @direct;
if has.mpc && has.control
    try
        % 보조 출력 L*x에 마지막 단계에서만 가중치를 주어 전체 P를 표현한다.
        L = chol(P);
        mdl = ss(A,B,[eye(4);L],zeros(8,1),Ts);
        obj = mpc(mdl,Ts,N,N);
        obj.Weights.OutputVariables = [sqrt(diag(Q))' zeros(1,4)];
        obj.Weights.ManipulatedVariables = sqrt(R);
        obj.Weights.ManipulatedVariablesRate = 1e-5;
        obj.MV.Min = -1; obj.MV.Max = 1;
        Y.Weight = [zeros(1,4) ones(1,4)];
        U.Weight = sqrt(R);
        setterminal(obj,Y,U);
        setoutdist(obj,'model',ss(zeros(8,1)));
        setEstimator(obj,'custom');
        state = mpcstate(obj);
        probe = [0;.05;0;0];
        assert(abs(toolbox_move(probe,0)-direct(probe,0))<1e-4, ...
            'MPC Toolbox와 직접 구현의 비용이 일치하지 않습니다.');
        fn = @toolbox_move;
        backend = "mpc";
    catch err
        warning('furuta:MPCToolbox','MPC 초기화 실패, 직접 풀이 사용 (%s)',err.message);
    end
end
    function u = direct(x,~)
        U = mpc_box(H,M*x,opts);
        u = U(1);
    end
    function u = toolbox_move(x,t)
        if t == 0
            state = mpcstate(obj);
        end
        state.Plant = x;
        u = mpcmove(obj,state,[],zeros(1,8));
    end
end
