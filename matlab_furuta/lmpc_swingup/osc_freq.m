function osc_freq(f)
d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
k=D(2,:)>0.5&D(3,:)>0.5&D(1,:)>5&D(1,:)<20; w=D(8,k); v=D(7,k); u=D(12,k); th=rad2deg(atan2(D(5,k),D(4,k)));
n=numel(w); F=(0:n-1)/(n*0.01); W=abs(fft(w-mean(w))); V=abs(fft(v-mean(v))); m=F>0.2&F<20;
[~,i]=max(W.*m); [~,j]=max(V.*m);
% fraction of time arm is stuck (|v|<0.05)
fprintf('%s: pend-rate peak %.2f Hz, arm-rate peak %.2f Hz, arm stuck frac %.2f, std th %.2f deg, |u| mean %.2f, u sign changes/s %.1f\n', ...
 f(end-30:end), F(i), F(j), mean(abs(v)<0.05), std(th), mean(abs(u)), nnz(diff(sign(u))~=0)/(n*0.01));
end
