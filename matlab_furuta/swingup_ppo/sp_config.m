function c = sp_config
% Shared plant/actuator/limit settings for the swing-up PPO work.
% Plant = comparison baseline used by the existing PPO candidates
% (alpha=0.05, eta_phi=1e-4, coulomb=0.63). These are NOT confirmed measurements.
p = furuta_params;
p.alpha = 0.05; p.eta_phi = 1e-4; p.coulomb = 0.63;
c.p = p;
c.Kt = 2.1;               % output-shaft nominal torque constant [N*m/A]
c.maxCurrent = 1.5;       % current command cap [A]
c.currentLSB = 0.01;      % A1 resolution [A]
c.p.tau_max = c.maxCurrent*c.Kt;
c.delaySteps = 1;         % 10 ms command delay
c.Ts = 0.01;
c.armRateLimitPC = 20;    % PC test arm limit (user prompt)
c.pendRateLimitPC = 25;   % PC test pendulum limit (user prompt)
c.armRateLimitTrain = 15; % stricter training termination (real-arm limit / no-load speed margin)
c.pendRateLimitTrain = 25;
end
