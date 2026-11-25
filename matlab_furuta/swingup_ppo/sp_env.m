classdef sp_env
% Batched lightweight-RMD environment: A1 quantization, +/-1.5 A clamp,
% integer-step command delay, RK4 (h=2 ms) plant. Matches furuta_rl_training RMD path.
methods (Static)
    function s = reset(x0,c)
        s.x = x0; n = size(x0,2);
        s.queue = zeros(max(c.delaySteps,1),n); % pending normalized commands
        s.t = zeros(1,n);
    end
    function [s,applied] = step(s,a,c)
        a = max(-1,min(1,a));
        % quantize request to A1 grid (same as Simulink: round(I/LSB))
        counts = round(a*c.maxCurrent/c.currentLSB);
        lim = floor(c.maxCurrent/c.currentLSB+1e-9);
        counts = max(-lim,min(lim,counts));
        cmd = counts*c.currentLSB/c.maxCurrent;
        if c.delaySteps>0
            applied = s.queue(1,:);
            s.queue = [s.queue(2:end,:); cmd];
        else
            applied = cmd;
        end
        tau = c.p.tau_max*applied;
        x = s.x; h = c.p.h; p = c.p;
        for i=1:round(c.Ts/h)
            k1=rhs(x); k2=rhs(x+h/2*k1); k3=rhs(x+h/2*k2); k4=rhs(x+h*k3);
            x = x+h/6*(k1+2*k2+2*k3+k4);
        end
        s.x = x; s.t = s.t+c.Ts;
        function y=rhs(z), y=[z(3:4,:); furuta_accel(z,tau,p)]; end
    end
    function o = obs(x)
        % [cos th; sin th; wrapped arm angle; arm rate; pend rate]
        o = [cos(x(2,:)); sin(x(2,:)); atan2(sin(x(1,:)),cos(x(1,:))); x(3,:); x(4,:)];
    end
end
end
