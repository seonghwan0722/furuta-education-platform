function quick_eval(tag)
addpath('C:/Capstone1/matlab_furuta/lmpc_swingup'); f=['C:/Capstone1/runs_pid/' tag '.mat'];
sum_pi_run(f); sum_bal(f,2.77);
d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
k=D(2,:)>0.5 & D(3,:)>0.5; t=D(1,k); th=rad2deg(atan2(D(5,k),D(4,k)))-2.77; m=t>4&t<20&abs(th)<10;
if nnz(m)>100, x=th(m)-mean(th(m)); X=abs(fft(x)); fq=(0:numel(x)-1)/(numel(x)*0.01); [~,i]=max(X(2:floor(end/2))); fprintf('dominant theta oscillation %.2f Hz, theta std in balance %.2f\n',fq(i+1),std(th(m))); end
end
