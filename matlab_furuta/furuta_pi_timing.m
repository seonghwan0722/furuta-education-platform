function row = furuta_pi_timing(t)
%#codegen
% Diagnostic timing log (2026-11-22): monotonic wall clock at each 5 ms base step on the Pi.
% row = [wall time since first step (s); step interval (ms); max interval so far (ms); count of intervals > 7.5 ms]
persistent first last maxdt late
if isempty(first)
    first = -1; last = 0; maxdt = 0; late = 0;
end
w = 0;
if coder.target('Rtw')
    here = 'C:/Capstone1/matlab_furuta';
    coder.updateBuildInfo('addSourceFiles','furuta_wallclock.c',here);
    coder.updateBuildInfo('addIncludePaths',here);
    coder.cinclude('furuta_wallclock.h');
    w = coder.ceval('furuta_wallclock');
end
if first < 0
    first = w; last = w;
end
dt = 1000*(w - last);
last = w;
if dt > maxdt, maxdt = dt; end
if dt > 7.5, late = late + 1; end
row = [w - first; dt; maxdt; late] + 0*t;
end
