function R = sp_rollout(policy,x0,T,c)
% policy: function handle (obs,x,mem)->(u,mem). Returns traces.
n=size(x0,2); N=round(T/c.Ts);
s=sp_env.reset(x0,c); mem.bal=false(1,n);
X=zeros(4,n,N+1); U=zeros(n,N); A=zeros(n,N); X(:,:,1)=x0;
for k=1:N
    [u,mem]=policy(sp_env.obs(s.x),s.x,mem);
    [s,ap]=sp_env.step(s,u,c);
    X(:,:,k+1)=s.x; U(:,k)=u; A(:,k)=ap;
end
R.X=X; R.U=U; R.A=A; R.t=(0:N)*c.Ts;
end
