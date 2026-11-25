function sum_bal(f,offDeg)
% Balance-quality summary using the trimmed angle (true = measured - offDeg)
d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
k=D(2,:)>0.5 & D(3,:)>0.5; t=D(1,k); th=rad2deg(atan2(D(5,k),D(4,k)))-offDeg; v=D(7,k); w=D(8,k); r=D(12,k); arm=rad2deg(D(6,k));
up=abs(th)<10; i0=find(up,1); m=t>t(i0)+0.5 & t<=20 & up;
ok=abs(th)<=5 & abs(w)<=0.5; c=0; best=0; bs=NaN; for j=1:numel(ok), if ok(j)&&t(j)<=20, c=c+1; if c>best, best=c; bs=t(j-c+1); end, else, c=0; end, end
fprintf('first |th|<10 at %.2f s; balance window %.1f s: mean th %.2f (std %.2f) deg, mean arm rate %.2f rad/s, arm travel %.0f deg, sat frac %.2f\n',t(i0),nnz(m)*0.01,mean(th(m)),std(th(m)),mean(v(m)),arm(find(t<=20,1,'last'))-arm(find(m,1)),mean(abs(r(m))>=0.99));
fprintf('criterion (|th|<=5 & |w|<=0.5, filtered w): longest run %.2f s starting %.2f s; PASS(>=5s & reach<=20s)=%d\n',best*0.01,bs,best*0.01>=5 && bs<=20);
end
