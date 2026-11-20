% unit check of furuta_pi_frame_tol (tolerance 2): misses 1-2 -> A1 zero, 3rd -> 0x80 latched
addpath('C:/Capstone1/matlab_furuta'); clear furuta_pi_frame_tol
lim=[Inf 3.3 15 25]; o=[1;0;0;0;0]; seq=[1 1 0 0 1 0 0 0 1 1]; r=[];
for k=1:numel(seq)
  [p,s,a]=furuta_pi_frame_tol(0.5,o,seq(k)==1,true,1,1.5,1.5,lim,0.1*k,20,2); r(end+1,:)=[seq(k) double(p(1)) a]; %#ok<AGROW>
end
disp(r)
clear furuta_pi_frame_tol; [p,~,~]=furuta_pi_frame_tol(0.5,[1;0;0;16;0],true,true,1,1.5,1.5,lim,0.1,20,2); fprintf('overspeed -> opcode %d (128 expected)\n',p(1));
clear furuta_pi_frame_tol; [p,~,~]=furuta_pi_frame_tol(0.5,o,false,true,1,1.5,1.5,lim,0.1,20,0); fprintf('tol0 first miss -> opcode %d (128 expected)\n',p(1));
