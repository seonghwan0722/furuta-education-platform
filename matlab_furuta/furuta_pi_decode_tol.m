function [obs, valid] = furuta_pi_decode_tol(frame, fresh, magnet, encoder, calibration, Ts)
%#codegen
% Variant of furuta_pi_decode used with MissTolerance>0 (2026-11-20).
% Same decoding and 30 ms rate filter. Difference: after 1-2 missed samples the filter state is kept
% and the next rate uses the true elapsed time (gap+1)*Ts, instead of resetting the rates to zero.
% After more than 2 consecutive misses it re-primes exactly like furuta_pi_decode.
persistent previous filtered primed home gap
if isempty(primed)
    previous = zeros(2,1);
    filtered = zeros(2,1);
    primed = false;
    home = NaN;
    gap = 0;
end
obs = zeros(5,1);
valid = false;
if ~fresh || frame(1) ~= 146 || bitand(magnet(1),uint8(56)) ~= 32
    gap = gap + 1;
    if gap > 2
        primed = false;
        filtered(:) = 0;
    end
    return
end
armBits = bitor(bitor(uint32(frame(5)),bitshift(uint32(frame(6)),8)), ...
    bitor(bitshift(uint32(frame(7)),16),bitshift(uint32(frame(8)),24)));
counts = double(bitand(encoder(1),uint8(15)))*256 + double(encoder(2));
rawDeg = double(typecast(armBits,'int32'))/100;
armHome = calibration(1);
if isnan(armHome)
    % Auto home: the first valid 0x92 angle of this run becomes arm zero (latched until restart).
    if isnan(home), home = rawDeg; end
    armHome = home;
end
arm = calibration(2)*(rawDeg-armHome)*pi/180;
pend = calibration(4)*(counts-calibration(3))*2*pi/4096;
pend = atan2(sin(pend),cos(pend));
if primed
    dt = Ts*(gap+1);
    delta = [arm;pend]-previous;
    delta(2) = atan2(sin(delta(2)),cos(delta(2)));
    filtered = filtered + (dt/(.03+dt))*(delta/dt-filtered);
    valid = true;
end
gap = 0;
previous = [arm;pend];
primed = true;
obs = [cos(pend);sin(pend);arm;filtered];
end
