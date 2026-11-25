function [electrical,angles,health] = furuta_pi_verify_sample(frame,rx,err,remote, ...
    magnet,magnetStatus,encoder,encoderStatus,cal,query,expected)
%#codegen
% Decode only the response for the current request. NaN marks missing values.
persistent lastElectrical rawArm received misses
if isempty(misses)
    lastElectrical = nan(5,1);
    rawArm = NaN;
    received = false(3,1);
    misses = 0;
end
if ~query
    matched = rx==1 && err==0 && remote==0 && frame(1)==expected;
    if ~matched
        misses = misses+1;
    end
    switch expected
        case 146
            received(1) = matched;
            rawArm = NaN;
            if matched
                bits = bitor(uint32(le16(frame(5),frame(6))), ...
                    bitshift(uint32(le16(frame(7),frame(8))),16));
                rawArm = double(typecast(bits,'int32'))/100;
            end
        case 154
            received(2) = matched;
            lastElectrical(1:2) = nan(2,1);
            if matched
                lastElectrical(1) = double(le16(frame(5),frame(6)))/10;
                lastElectrical(2) = double(le16(frame(7),frame(8)));
            end
        case 156
            received(3) = matched;
            lastElectrical(3:5) = nan(3,1);
            if matched
                lastElectrical(3) = double(typecast(le16(frame(3),frame(4)),'int16'))/100;
                lastElectrical(4) = double(typecast(le16(frame(5),frame(6)),'int16'));
                lastElectrical(5) = double(typecast(frame(2),'int8'));
            end
    end
end
magnetOK = magnetStatus==0 && bitand(magnet(1),uint8(56))==32;
pendOK = magnetOK && encoderStatus==0;
counts = NaN;
pend = NaN;
if pendOK
    counts = double(bitand(encoder(1),uint8(15)))*256+double(encoder(2));
    pend = mod(cal(4)*(counts-cal(3))*360/4096+180,360)-180;
end
electrical = lastElectrical;
angles = [rawArm;cal(2)*(rawArm-cal(1));counts;pend];
voltageOK = received(2) && electrical(1)>=46 && electrical(1)<=50;
healthy = all(received) && pendOK && voltageOK && electrical(2)==0;
health = [double(received);double(magnetOK);double(pendOK);double(voltageOK); ...
    double(healthy);misses;double(magnet(1));double(magnetStatus);double(encoderStatus);double(err)];
end

function v = le16(low,high)
v = bitor(uint16(low),bitshift(uint16(high),8));
end
