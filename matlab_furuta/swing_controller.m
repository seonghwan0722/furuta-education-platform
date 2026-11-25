function fn = swing_controller(balance,reset,capture)
% 입력이 양수일 때 직립 근처 진자 가속도는 음수다.
% 따라서 E<0에서 kE>0이면 평균적으로 에너지가 증가한다.
if nargin<3, capture = [deg2rad(20) Inf]; end
p = furuta_params; balancing = false;
fn = @control;
    function u = control(x,t)
        x(2) = wrap_theta(x(2));
        if t == 0
            balancing = false;
            if ~isempty(reset)
                reset();
            end
        end
        if balancing && abs(x(2))>deg2rad(30)
            balancing = false;
        elseif ~balancing && abs(x(2))<=capture(1) && abs(x(4))<=capture(2)
            balancing = true;
            if ~isempty(reset)
                reset();
            end
        end
        if balancing
            u = balance(x,t);
        else
            E = .5*p.beta2*x(4)^2+p.delta*(cos(x(2))-1);
            direction = sign(x(4)*cos(x(2)));
            if t == 0 && abs(x(4))<1e-8
                direction = 1; % 정지 평형에서 최초 한 틱의 기동 입력
            end
            u = max(-1,min(1,247*E*direction));
        end
    end
end
