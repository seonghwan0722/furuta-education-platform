function [z, s] = cem_randn(s, n)
% n standard normals from xorshift32 + Box-Muller (cos, sin pairs).
% Bit-identical to cem.py randn_fill so MATLAB and Python draw the same samples.
z = zeros(n,1); i = 1;
while i <= n
    s = cem_xs32(s); u1 = (double(s) + 1) / 4294967297;
    s = cem_xs32(s); u2 = double(s) / 4294967296;
    r = sqrt(-2*log(u1)); t = 2*pi*u2;
    z(i) = r*cos(t);
    if i + 1 <= n, z(i+1) = r*sin(t); end
    i = i + 2;
end
end

function s = cem_xs32(s)
% xorshift32 (13, 17, 5); bits shifted past bit 31 are dropped, as in C. Done in uint64 to avoid saturation.
m = uint64(4294967295); x = uint64(s);
x = bitxor(x, bitand(bitshift(x, 13), m));
x = bitxor(x, bitshift(x, -17));
x = bitxor(x, bitand(bitshift(x, 5), m));
s = uint32(x);
end
