function [obs, valid, acknowledged] = furuta_pi_sample(frame,status,busError,remote, ...
    magnet,magnetStatus,encoder,encoderStatus,calibration,actPhase)
%#codegen
persistent lastObs confirmed
if isempty(confirmed)
    lastObs = zeros(5,1);
    confirmed = false;
end
fresh = status == 1 && busError == 0 && remote == 0;
valid = false;
if actPhase
    ok = fresh && magnetStatus == 0 && encoderStatus == 0;
    [lastObs,valid] = furuta_pi_decode(frame,ok,magnet,encoder,calibration,.01);
else
    confirmed = fresh && frame(1) == 161;
end
obs = lastObs;
acknowledged = confirmed;
end
