function sum_timing(f)
% Summarize furutaPiTiming (wall clock per 5 ms step) and relate late steps to CAN misses.
d=load(f); T=d.L.getElement('furutaPiTiming').Values; X=squeeze(T.Data); if size(X,1)>size(X,2), X=X.'; end
t=T.Time(:)'; dt=X(2,:); k=t>0.02;
fprintf('steps %d | interval mean %.3f ms, std %.3f, p99 %.3f, max %.2f ms at t=%.3f s | >7.5 ms: %d, >10 ms: %d, >20 ms: %d\n', ...
  nnz(k),mean(dt(k)),std(dt(k)),prctile(dt(k),99),max(dt(k)),t(find(k & dt==max(dt(k)),1)),nnz(k&dt>7.5),nnz(k&dt>10),nnz(k&dt>20));
fprintf('wall time at model t=20 s: %.3f s (drift %.1f ms)\n',interp1(t,X(1,:),20),1000*(interp1(t,X(1,:),20)-20+t(find(k,1))));
H=d.L.getElement('furutaPiHealth').Values; Hd=squeeze(H.Data); if size(Hd,1)>size(Hd,2), Hd=Hd.'; end
miss=H.Time(Hd(1,:)==0 & H.Time'>0.02)';
for m=miss, j=find(abs(t-m)<0.0151); fprintf('CAN miss at %.3f s: nearby intervals %s ms\n',m,mat2str(round(dt(j)*100)/100)); end
late=t(k&dt>7.5); fprintf('late steps at: %s\n',mat2str(round(late(1:min(30,end))*1000)/1000));
end
