function S = analyze_pi_ctrl_run(matFile)
% Summarize a Pi controller run (furutaPiTelemetry rows: [t; act; valid; obs(5); a; opcode; ack; requested]).
d=load(matFile); L=d.L; names=L.getElementNames; fprintf('signals: %s\n',strjoin(names,', '));
e=L.getElement('furutaPiTelemetry'); v=e.Values; D=squeeze(v.Data); if size(D,1)>size(D,2), D=D.'; end
t=D(1,:); act=D(2,:)>0.5; valid=D(3,:)>0.5; obs=D(4:8,:); a=D(9,:); op=D(10,:); ack=D(11,:); req=D(12,:);
k=act; th=rad2deg(atan2(obs(2,k),obs(1,k))); arm=rad2deg(obs(3,k)); vr=obs(4,k); wr=obs(5,k); u=req(k); ua=a(k); tk=t(k); vk=valid(k);
fprintf('duration %.1f s, act samples %d, valid %.1f%%, opcodes %s\n',t(end)-t(1),nnz(k),100*mean(vk),mat2str(unique(op)));
fprintf('pend angle range %.1f..%.1f deg, arm range %.1f..%.1f deg\n',min(th),max(th),min(arm),max(arm));
hang=abs(abs(th)-180)<10 & vk; up=abs(th)<15 & vk;
fprintf('hanging samples %d (mean |th| %.2f deg), upright samples %d\n',nnz(hang),mean(abs(th(hang))),nnz(up));
if nnz(up)>20
  c=corrcoef(th(up),u(up)); p=polyfit(th(up),u(up),1);
  fprintf('UPRIGHT: corr(theta,action)=%.2f slope %.3f /deg (PID nominal +0.437/deg), action range %.2f..%.2f\n',c(1,2),p(1),min(u(up)),max(u(up)));
  fprintf('UPRIGHT: theta mean %.2f deg (hand-held), filtered pend-rate std %.2f rad/s\n',mean(th(up)),std(wr(up)));
end
fprintf('action nonzero fraction %.2f, max|action| %.2f\n',mean(abs(u)>0),max(abs(u)));
S=struct('t',tk,'th',th,'arm',arm,'u',u,'valid',vk);
f=figure('Visible','off','Position',[100 100 1000 700]); tiledlayout(3,1);
nexttile; plot(tk-tk(1),th); ylabel('pend (deg)'); grid on; title(strrep(matFile,'_','\_'));
nexttile; plot(tk-tk(1),arm); ylabel('arm (deg)'); grid on;
nexttile; plot(tk-tk(1),u); ylabel('action'); xlabel('t (s)'); grid on;
exportgraphics(f,strrep(matFile,'.mat','.png'),'Resolution',100); close(f);
end
