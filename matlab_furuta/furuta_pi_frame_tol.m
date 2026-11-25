function [payload, send, actionSent] = furuta_pi_frame_tol(action, obs, valid, ...
    armed, currentSign, ampsPerAction, maxAmps, limits, t, driveSeconds, missTol)
%#codegen
% RMD payload with a bounded tolerance for missed CAN/sensor samples (user decision 2026-11-20).
% Same as furuta_pi_frame, except: when the sample is not valid (no fresh reply / no ack),
% up to missTol consecutive ticks send a 0 A torque command instead of latching.
% The (missTol+1)-th consecutive miss latches Motor Off. Speed, angle and drive-time limits
% still latch Motor Off on the first violation. A latched fault sends Motor Off until the model stops.
persistent fault miss
if isempty(fault)
    fault = false;
    miss = 0;
end
payload = zeros(1,8,'uint8');
send = false;
actionSent = 0;
if ~armed
    return
end
commOk = valid && all(isfinite(obs));
if commOk
    miss = 0;
elseif ~fault
    miss = miss + 1;
    if miss <= missTol && t < driveSeconds
        % hold-off tick: explicit zero torque (A1 with 0 counts), no limit check on a stale sample
        send = true;
        payload(1) = uint8(161);
        return
    end
end
safe = commOk && isfinite(action) && ...
    abs(obs(3)) < limits(1) && abs(atan2(obs(2),obs(1))) < limits(2) && ...
    abs(obs(4)) < limits(3) && abs(obs(5)) < limits(4) && t < driveSeconds && ...
    abs(currentSign) == 1 && ampsPerAction > 0 && maxAmps >= .01;
fault = fault || ~safe;
send = true;
if fault
    payload(1) = uint8(128);
    return
end
bounded = max(-1,min(1,action));
limitCounts = min(32767,floor(100*maxAmps));
counts = int16(max(-limitCounts,min(limitCounts,round(100*ampsPerAction*currentSign*bounded))));
bits = typecast(counts,'uint16');
payload(1) = uint8(161);
payload(5) = uint8(bitand(bits,uint16(255)));
payload(6) = uint8(bitshift(bits,-8));
actionSent = double(counts)*currentSign/(100*ampsPerAction);
end
