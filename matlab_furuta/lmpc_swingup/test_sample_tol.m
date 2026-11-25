% Synthetic replay: replies alternate 0x92 (146) / 0xA1 (161); at slot 41 one reply is missing and every later
% reply is read one slot late (as seen on hardware 2026-11-20). Compare original vs tolerant decoder.
addpath('C:/Capstone1/matlab_furuta');
cal=[NaN 1 2048 1]; mag=uint8([32 0]); N=120;
armDeg=@(t) 10*t;  % 10 deg/s ramp
for variant=1:2
  clear furuta_pi_sample furuta_pi_decode furuta_pi_sample_tol furuta_pi_decode_tol
  V=[]; A=[]; R=[];
  for k=1:N
    t=k*0.005; act=mod(k,2)==1;
    lagged = k>=41;
    if k==41, st=0; fr=zeros(1,8,'uint8');
    else
      st=1; isAng = act ~= lagged;            % normal: angle reply read in act slot; lagged: in query slot
      if isAng
        tr = t - lagged*0.005;                 % lagged angle is one slot older
        b=typecast(int32(round(armDeg(tr)*100)),'uint8'); fr=uint8([146 0 0 0 b]);
      else, fr=uint8([161 0 0 0 0 0 0 0]); end
    end
    enc=uint8([8 0]);  % counts 2048 -> pendulum 0
    if variant==1, [o,v,a]=furuta_pi_sample(fr,st,0,0,mag,0,enc,0,cal,act);
    else, [o,v,a]=furuta_pi_sample_tol(fr,st,0,0,mag,0,enc,0,cal,act); end
    if act, V(end+1)=v; A(end+1)=a; R(end+1)=o(4); end %#ok<AGROW>
  end
  fprintf('variant %d: valid act ticks after the miss %d/%d, invalid run %s, ack after miss %d/%d, arm rate at end %.3f rad/s (true %.3f)\n', ...
    variant,nnz(V(21:end)),numel(V(21:end)),mat2str(find(~V)),nnz(A(22:end)),numel(A(22:end)),R(end),deg2rad(10));
end
