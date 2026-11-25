function [payload,send,target] = furuta_pi_speed_frame(rpm,obs,valid,armed, ...
    armSign,maxRPM,currentPercent,limits,t,driveSeconds)
%#codegen
% The RMD closes the speed loop. A fault stays latched until restart.
persistent fault
if isempty(fault)
    fault = false;
end
payload = zeros(1,8,'uint8');
send = false;
target = max(-maxRPM,min(maxRPM,rpm));
if ~armed
    return
end
safe = valid && all(isfinite(obs)) && isfinite(rpm) && abs(armSign)==1 && ...
    currentPercent>=1 && currentPercent<=255 && ...
    abs(obs(3))<limits(1) && abs(atan2(obs(2),obs(1)))<limits(2) && ...
    abs(obs(4))<limits(3) && abs(obs(5))<limits(4) && t<driveSeconds;
fault = fault || ~safe;
send = true;
if fault || target==0
    payload(1) = uint8(128);
    target = 0;
    return
end
bits = typecast(int32(round(armSign*target*600)),'uint32');
payload(1) = uint8(162);
payload(2) = uint8(currentPercent);
for k=0:3
    payload(5+k) = uint8(bitand(bitshift(bits,-8*k),uint32(255)));
end
end
