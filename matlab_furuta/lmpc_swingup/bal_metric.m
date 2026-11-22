function S = bal_metric(R,t0)
% Balance quality from a rollout, using the Pi-style observation (filtered pend rate), after t0 seconds.
n=size(R.X,2); N=size(R.O,3); k0=round(t0/0.01)+1; S=zeros(n,5);
for j=1:n
  th=squeeze(atan2(sin(R.X(2,j,2:end)),cos(R.X(2,j,2:end))))'; w=squeeze(R.O(5,j,:))'; u=R.U(j,:);
  ok=abs(th)<=deg2rad(5) & abs(w)<=0.5; c=0; b=0; for k=k0:N, if ok(k), c=c+1; b=max(b,c); else, c=0; end, end
  S(j,:)=[b*0.01, mean(abs(w(k0:N))>0.5), rad2deg(std(th(k0:N))), nnz(diff(sign(u(k0:N)))~=0)/((N-k0)*0.01), max(abs(th(k0:N)))*180/pi];
end
end
