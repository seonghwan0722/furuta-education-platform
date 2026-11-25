function [obs, valid, acknowledged] = furuta_pi_sample_tol(frame,status,busError,remote, ...
    magnet,magnetStatus,encoder,encoderStatus,calibration,actPhase)
%#codegen
% Variant of furuta_pi_sample used with MissTolerance>0 (2026-11-20).
% Hardware runs ppo_rev11b_tol2_16 / ppo_rev11_12 showed that after one late RMD reply every later
% reply is read one 5 ms slot late (0x92 angle reply in the query slot, 0xA1 ack in the act slot),
% so the slot-based decoder rejected every sample from then on. Here replies are sorted by opcode:
%  - a 0x92 (146) frame seen in this or the previous slot is used at the next act slot,
%  - a 0xA1 (161) frame seen since the last act slot counts as the acknowledgement.
persistent lastObs ackSeen angFrame angNew
if isempty(ackSeen)
    lastObs = zeros(5,1);
    ackSeen = false;
    angFrame = zeros(1,8,'uint8');
    angNew = false;
end
fresh = status == 1 && busError == 0 && remote == 0;
if fresh && frame(1) == 161
    ackSeen = true;
end
if fresh && frame(1) == 146
    angFrame = frame;
    angNew = true;
end
valid = false;
acknowledged = ackSeen;
if actPhase
    ok = angNew && magnetStatus == 0 && encoderStatus == 0;
    [lastObs,valid] = furuta_pi_decode_tol(angFrame,ok,magnet,encoder,calibration,.01);
    angNew = false;
    ackSeen = false;   % next act slot needs the ack of the command sent now
end
obs = lastObs;
end
