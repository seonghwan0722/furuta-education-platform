function [payload, send, actionSent] = furuta_pi_frame(action, obs, valid, ...
    armed, currentSign, ampsPerAction, maxAmps, limits, t, driveSeconds)
%#codegen
% RMD payload. A latched fault sends Motor Off until the model stops.
persistent fault
if isempty(fault)
    fault = false;
end
payload = zeros(1,8,'uint8');
send = false;
actionSent = 0;
if ~armed
    return
end
safe = valid && all(isfinite(obs)) && isfinite(action) && ...
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
