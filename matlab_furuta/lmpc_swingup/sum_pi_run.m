function sum_pi_run(f)
d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
t=D(1,:); k=D(2,:)>0.5; vk=D(3,:)>0.5;
iv=find(k & ~vk & t>0.05,1); i80=find(D(10,:)==128,1); n161=nnz(D(10,:)==161);
fprintf('valid %.1f%% | first invalid %s | first 0x80 %s | 0xA1 count %d\n',100*mean(D(3,k)),num2str(t(iv)),num2str(t(i80)),n161);
kk=k&vk; th=rad2deg(atan2(D(5,kk),D(4,kk))); arm=rad2deg(D(6,kk)); v=D(7,kk); w=D(8,kk); r=D(12,kk); tt=t(kk);
fprintf('max|v| %.2f max|w| %.2f, min|th| %.1f deg, time |th|<10: %.2f s, longest |th|<5 run %.2f s\n',max(abs(v)),max(abs(w)),min(abs(th)),0.01*nnz(abs(th)<10),0.01*maxrun(abs(th)<5));
try, H=d.L.getElement('furutaPiHealth').Values; Hd=squeeze(H.Data); if size(Hd,1)>size(Hd,2), Hd=Hd.'; end
 q=find(Hd(1,:)==0 & H.Time'>0.05,1); if ~isempty(q), fprintf('CAN reply lost at %.3f s\n',H.Time(q)); else, fprintf('CAN replies OK throughout\n'); end; catch, end
for s=0:1:min(20,floor(tt(end)-tt(1))), j=find(tt-tt(1)>=s,1); fprintf('t=%4.1f th=%7.1f arm=%8.1f v=%6.2f w=%6.2f req=%5.2f\n',tt(j)-tt(1),th(j),arm(j),v(j),w(j),r(j)); end
end
function m=maxrun(b), m=0; c=0; for x=b, if x, c=c+1; m=max(m,c); else, c=0; end, end, end
