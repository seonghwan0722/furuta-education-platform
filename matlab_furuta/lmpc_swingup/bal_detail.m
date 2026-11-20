function bal_detail(f,offDeg,t0,t1)
d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
k=D(2,:)>0.5 & D(3,:)>0.5; t=D(1,k); th=rad2deg(atan2(D(5,k),D(4,k)))-offDeg; v=D(7,k); w=D(8,k); r=D(12,k);
m=t>=t0 & t<=t1;
fprintf('window %.1f-%.1f s: |th|>5 frac %.3f, |w|>0.5 frac %.3f, both-ok frac %.3f, max|th| %.2f, max|w| %.2f, std w %.3f, mean|v| %.2f max|v| %.2f, max|u| %.2f\n', ...
 t0,t1,mean(abs(th(m))>5),mean(abs(w(m))>0.5),mean(abs(th(m))<=5&abs(w(m))<=0.5),max(abs(th(m))),max(abs(w(m))),std(w(m)),mean(abs(v(m))),max(abs(v(m))),max(abs(r(m))));
bad=find(m & (abs(th)>5 | abs(w)>0.5)); fprintf('bad sample times: %s\n',mat2str(round(t(bad(1:min(40,end)))*100)/100));
f2=figure('Visible','off','Position',[100 100 1100 800]); tiledlayout(4,1);
nexttile; plot(t,th); ylabel('pend err (deg)'); grid on; xlim([0 t(end)]); yline([-5 5],'r:');
nexttile; plot(t,w); ylabel('pend rate'); grid on; xlim([0 t(end)]); yline([-.5 .5],'r:'); ylim([-3 3]);
nexttile; plot(t,v); ylabel('arm rate'); grid on; xlim([0 t(end)]);
nexttile; plot(t,r*1.5); ylabel('cmd (A)'); xlabel('t (s)'); grid on; xlim([0 t(end)]);
exportgraphics(f2,strrep(f,'.mat','_detail.png'),'Resolution',110); close(f2);
end
