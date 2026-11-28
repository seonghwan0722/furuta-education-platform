/* Educational classical control. Uses the existing nonlinear PS.Furuta plant.
 * State x = [arm angle, upright pendulum error, arm rate, pendulum rate].
 * LQR: discrete DARE. LMPC: finite-horizon input-constrained quadratic program,
 * solved by a primal feasible active-set method; apply the first input.
 * Hardware export contains controller numbers only; hardware I/O lives outside this file.
 * Balance experiments retain their original behavior; automatic swing-up is
 * available as a separate hybrid experiment and an explicitly exported candidate.
 */
(function (PS) {
  'use strict';
  const zeros = (r, c) => Array.from({length:r}, () => Array(c).fill(0));
  const eye = n => zeros(n,n).map((r,i) => r.map((_,j) => +(i===j)));
  const tr = A => A[0].map((_,j) => A.map(r=>r[j]));
  const mm = (A,B) => A.map(r=>B[0].map((_,j)=>r.reduce((s,v,k)=>s+v*B[k][j],0)));
  const mv = (A,x) => A.map(r=>dot(r,x));
  const dot = (a,b) => a.reduce((s,v,i)=>s+v*b[i],0);
  const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
  const deg = x => x*180/Math.PI;
  const IDEAL = {Fp:0,Fm:0,b:0.02,pend_fl:0,lat:0,kt:1,zero_deg:0};
  const defaults = {method:'pid',plant:'ideal',angle:5,seconds:10,limit:0.8,
    p:1,i:0,d:1,arm:1,qAngle:40,qArm:0.5,r:1,horizon:20,
    disturbance:0,antiWindup:true};

  function options(v) {
    const o=Object.assign({},defaults,v);
    if (!['pid','lqr','lmpc'].includes(o.method) || !['ideal','calibrated'].includes(o.plant)) throw Error('Unknown experiment mode');
    const limits={angle:[-30,30],seconds:[2,20],limit:[0.05,1],p:[0,3],i:[0,3],d:[0,3],arm:[0,2],qAngle:[1,200],qArm:[0.05,10],r:[0.1,20],horizon:[5,40],disturbance:[-0.3,0.3]};
    for (const k in limits) {
      if (!Number.isFinite(+o[k])) throw Error('Invalid '+k);
      o[k]=clamp(+o[k],limits[k][0],limits[k][1]);
    }
    o.horizon=Math.round(o.horizon);
    return o;
  }
  function state(sim,mode) {
    return mode==='calibrated'
      ? [sim.mTh,PS.wrap(sim.mAl-Math.PI),sim.mThd,sim.mAld]
      : [sim.th,sim.phi(),sim.thd,sim.ald];
  }
  function plant(C,mode) { return new PS.Furuta(C,mode==='ideal'?IDEAL:{}); }
  function advance(sim,u,mode) {
    if(mode==='calibrated') return sim.step(u);
    // Isolate controller principles: smooth friction, exact state, continuous torque.
    sim.u=clamp(u,-1,1); sim.tau=sim.u*sim.C.tau_max;
    for(let j=0;j<sim.sub;j++) sim.substep(sim.tau);
    sim.t+=sim.ctrlDt;
    sim.dead=Math.abs(sim.thd)>sim.C.arm_speed_lim || Math.abs(sim.ald)>sim.C.pend_speed_lim;
    return sim;
  }
  function linearize(C) {
    function f(x,u) {
      const s=plant(C,'ideal').reset(x[0],Math.PI+x[1],x[2],x[3]);
      advance(s,u,'ideal');return state(s,'ideal');
    }
    const e=1e-5,A=zeros(4,4);
    for(let j=0;j<4;j++){
      let xp=[0,0,0,0],xm=[0,0,0,0];xp[j]=e;xm[j]=-e;
      const p=f(xp,0),m=f(xm,0);
      for(let i=0;i<4;i++) A[i][j]=(p[i]-m[i])/(2*e);
    }
    const p=f([0,0,0,0],e),m=f([0,0,0,0],-e);
    return {A,B:p.map((v,i)=>(v-m[i])/(2*e)),dt:1/C.ctrl_hz};
  }
  function lqr(A,B,q,R) {
    const Q=q.map((v,i)=>q.map((_,j)=>i===j?v:0)),At=tr(A);
    let P=Q.map(r=>r.slice()),K,delta=Infinity,iterations=0;
    for(;iterations<10000;iterations++){
      const PA=mm(P,A),PB=mv(P,B),d=R+dot(B,PB);
      K=mv(tr(PA),B).map(v=>v/d);
      const BtPA=mv(tr(PA),B),APA=mm(At,PA);
      const raw=APA.map((r,i)=>r.map((v,j)=>Q[i][j]+v-BtPA[i]*K[j]));
      const next=raw.map((r,i)=>r.map((v,j)=>(v+raw[j][i])/2));
      delta=Math.max(...next.flatMap((r,i)=>r.map((v,j)=>Math.abs(v-P[i][j]))))/Math.max(1,...next.flat().map(Math.abs));
      P=next;if(delta<1e-10)break;
    }
    if(!Number.isFinite(delta) || delta>1e-6)throw Error('LQR design did not converge');
    K=mv(tr(mm(P,A)),B).map(v=>v/(R+dot(B,mv(P,B))));
    return {K,P,iterations,delta};
  }
  function mpcSetup(A,B,q,R,N,P) {
    const H=zeros(N,N),F=zeros(N,4);
    let S=eye(4),G=zeros(4,N);
    for(let k=0;k<N;k++){
      S=mm(A,S);G=mm(A,G);for(let i=0;i<4;i++)G[i][k]+=B[i];
      const W=k===N-1?P:q.map((v,i)=>q.map((_,j)=>i===j?v:0));
      const GtW=mm(tr(G),W),h=mm(GtW,G),f=mm(GtW,S);
      for(let i=0;i<N;i++){
        for(let j=0;j<N;j++)H[i][j]+=h[i][j];
        for(let j=0;j<4;j++)F[i][j]+=f[i][j];
      }
    }
    for(let i=0;i<N;i++)H[i][i]+=R;
    return {H,F,A,B,N};
  }
  function solveSPD(A,b) {
    const n=b.length,L=zeros(n,n);
    for(let i=0;i<n;i++)for(let j=0;j<=i;j++){
      let v=A[i][j];for(let k=0;k<j;k++)v-=L[i][k]*L[j][k];
      L[i][j]=i===j?Math.sqrt(Math.max(v,1e-14)):v/L[j][j];
    }
    const y=Array(n).fill(0),x=Array(n).fill(0);
    for(let i=0;i<n;i++){y[i]=b[i];for(let j=0;j<i;j++)y[i]-=L[i][j]*y[j];y[i]/=L[i][i];}
    for(let i=n-1;i>=0;i--){x[i]=y[i];for(let j=i+1;j<n;j++)x[i]-=L[j][i]*x[j];x[i]/=L[i][i];}
    return x;
  }
  function solveQP(H,f,limit,initial,maxSweeps=200) {
    const n=f.length,u=Array.from({length:n},(_,i)=>clamp(initial?initial[i]:0,-limit,limit));
    const active=u.map(v=>v<=-limit+1e-10?-1:v>=limit-1e-10?1:0);
    let residual=Infinity,sweep=0;
    for(;sweep<maxSweeps;sweep++){
      const grad=H.map((r,i)=>dot(r,u)+f[i]);
      const free=Array.from({length:n},(_,i)=>i).filter(i=>active[i]===0);
      let stationary=true;
      if(free.length){
        const d=solveSPD(free.map(i=>free.map(j=>H[i][j])),free.map(i=>-grad[i]));
        stationary=Math.max(...free.map(i=>Math.abs(grad[i])))<1e-7;
        if(!stationary){
          let step=1,hit=-1,side=0;
          free.forEach((i,k)=>{
            const bound=d[k]>1e-15?(limit-u[i])/d[k]:d[k]<-1e-15?(-limit-u[i])/d[k]:Infinity;
            if(bound<step){step=Math.max(0,bound);hit=i;side=d[k]>0?1:-1;}
          });
          free.forEach((i,k)=>{u[i]=clamp(u[i]+step*d[k],-limit,limit);});
          if(hit>=0){u[hit]=side*limit;active[hit]=side;}
        }
      }
      // At a free-variable stationary point, release the bound whose KKT
      // multiplier has the wrong sign. Bound variables are not released together:
      // that would allow zero-length Newton steps and stall at a corner.
      if(stationary){
        let release=-1,violation=1e-7;
        for(let i=0;i<n;i++)if(active[i]){
          const bad=active[i]===-1?-grad[i]:grad[i];
          if(bad>violation){violation=bad;release=i;}
        }
        if(release>=0)active[release]=0;
      }
      residual=0;
      for(let i=0;i<n;i++){
        const g=dot(H[i],u)+f[i];
        const kkt=u[i]<=-limit+1e-10?Math.min(g,0):u[i]>=limit-1e-10?Math.max(g,0):g;
        residual=Math.max(residual,Math.abs(kkt));
      }
      if(residual<1e-6)break;
    }
    return {u,residual,iterations:sweep+1,converged:residual<1e-5};
  }
  function controller(C,raw) {
    const o=options(raw),lm=linearize(C),q=[o.qArm,o.qAngle,0.3,1];
    const design=lqr(lm.A,lm.B,q,o.r);
    // A fixed reference design gives meaningful P/D scales; they remain independent of the LQR sliders.
    const base=lqr(lm.A,lm.B,[0.5,40,0.3,1],1);
    const mp=o.method==='lmpc'?mpcSetup(lm.A,lm.B,q,o.r,o.horizon,design.P):null;
    let integral=0,warm=Array(o.horizon).fill(0);
    const self={o,design,lm,last:{}};
    self.step=function(x){
      if(!x.every(Number.isFinite))throw Error('Non-finite plant state');
      let requested,parts={},plan=null,qp=null;
      if(o.method==='pid'){
        const candidate=clamp(integral+x[1]*lm.dt,-1,1);
        const ki=base.K[1]*o.i;
        parts={P:-base.K[1]*o.p*x[1],I:-ki*candidate,D:-base.K[3]*o.d*x[3],arm:-o.arm*(base.K[0]*x[0]+base.K[2]*x[2])};
        requested=parts.P+parts.I+parts.D+parts.arm;
        const deltaI=-ki*(candidate-integral);
        if(!o.antiWindup || Math.abs(requested)<=o.limit || requested*deltaI<0)integral=candidate;
        parts.I=-ki*integral;requested=parts.P+parts.I+parts.D+parts.arm;
      }else if(o.method==='lqr'){
        parts={arm:-design.K[0]*x[0],angle:-design.K[1]*x[1],armRate:-design.K[2]*x[2],pendRate:-design.K[3]*x[3]};
        requested=-dot(design.K,x);
      }else{
        qp=solveQP(mp.H,mv(mp.F,x),o.limit,warm);
        // The feasible iterate is retained if tolerance is not reached, and exposed in telemetry.
        requested=qp.u[0];warm=qp.u.slice(1).concat(qp.u.at(-1));
        let z=x.slice();plan=[z.slice()];
        for(const u of qp.u){z=mv(mp.A,z).map((v,i)=>v+mp.B[i]*u);plan.push(z.slice());}
      }
      const u=clamp(requested,-o.limit,o.limit);
      self.last={requested,u,parts,plan,qp,integral};return u;
    };
    return self;
  }
  function experiment(C,raw) {
    const o=options(raw),ctrl=controller(C,o),sim=plant(C,o.plant).reset(0,Math.PI+o.angle*Math.PI/180,0,0);
    const rows=[];let stopped=false,reason='',sumError=0,sumU=0,maxU=0,sat=0,held=0,longest=0,qpFailures=0;
    const self={o,ctrl,sim,rows};
    self.tick=function(){
      if(stopped)return false;
      const x=state(sim,o.plant),u=ctrl.step(x);
      if(o.disturbance && sim.t>=2 && sim.t<2+sim.ctrlDt/2)sim.ald+=o.disturbance;
      advance(sim,u,o.plant);
      const error=deg(sim.phi()),valid=[sim.th,sim.al,sim.thd,sim.ald,u].every(Number.isFinite);
      if(!valid){stopped=true;reason='수치 오류';return false;}
      const inBand=Math.abs(error)<=5 && Math.abs(sim.ald)<=0.5;
      held=inBand?held+sim.ctrlDt:0;longest=Math.max(longest,held);
      sumError+=Math.abs(error);sumU+=u*u;maxU=Math.max(maxU,Math.abs(u));if(Math.abs(ctrl.last.requested)>=o.limit-1e-8)sat++;
      if(ctrl.last.qp&&!ctrl.last.qp.converged)qpFailures++;
      rows.push({t:sim.t,error,arm:deg(sim.th),armRate:sim.thd,pendRate:sim.ald,u,tau:sim.tau,requested:ctrl.last.requested});
      if(sim.dead){stopped=true;reason='속도 제한 도달';}
      else if(Math.abs(error)>60){stopped=true;reason='직립 학습 범위 이탈 (60°)';}
      else if(sim.t>=o.seconds-1e-8){stopped=true;reason='완료';}
      return !stopped;
    };
    self.summary=()=>({method:o.method,plant:o.plant,status:reason||'진행 중',duration:sim.t,
      meanError:rows.length?sumError/rows.length:0,rmsAction:rows.length?Math.sqrt(sumU/rows.length):0,
      maxAction:maxU,saturation:rows.length?100*sat/rows.length:0,longest,qpFailures,parameters:Object.assign({},o)});
    self.done=()=>stopped;
    return self;
  }
  /* Export the same classroom controller, in normalized torque units, for the
   * Pi to evaluate locally. This is a design export, not physical validation.
   * Angle/disturbance/plant in parameters document the lesson; they never ask
   * hardware to move to that initial pose or inject a simulated disturbance. */
  function buildHardwareConfig(C,raw) {
    const o=options(raw);
    if(C.name!=='rev11' || Math.abs(1/C.ctrl_hz-.02)>1e-12 || Math.abs(C.tau_max-2.52)>1e-12)
      throw Error('실물 제어기는 rev11 · 50 Hz · 2.52 N·m 기준에서만 내보낼 수 있습니다.');
    if(typeof o.antiWindup!=='boolean')throw Error('누적 제한 설정을 확인해 주세요.');
    const lm=linearize(C);
    let exported;
    if(o.method==='pid'){
      const base=lqr(lm.A,lm.B,[0.5,40,0.3,1],1);
      exported={kp:base.K[1]*o.p,ki:base.K[1]*o.i,kd:base.K[3]*o.d,
        karm:base.K[0]*o.arm,karmRate:base.K[2]*o.arm,antiWindup:o.antiWindup};
    }else{
      const q=[o.qArm,o.qAngle,0.3,1],design=lqr(lm.A,lm.B,q,o.r);
      exported=o.method==='lqr'?{K:design.K.slice()}:
        {A:lm.A.map(row=>row.slice()),B:lm.B.slice(),Q:q,R:o.r,P:design.P.map(row=>row.slice()),N:o.horizon};
    }
    const config={schema:1,kind:'furuta-classical',model:'rev11-control-lab-upright-v1',method:o.method,
      dt:lm.dt,tau_max:C.tau_max,limit:o.limit,state:['theta','upright_error','theta_dot','alpha_dot'],
      parameters:Object.fromEntries(Object.keys(defaults).map(key=>[key,o[key]])),controller:exported,swingup:buildSwingConfig(C)};
    function finite(value){
      if(typeof value==='number'&&!Number.isFinite(value))throw Error('제어기 계산값이 유한하지 않습니다.');
      if(value&&typeof value==='object')Object.values(value).forEach(finite);
    }
    finite(config);
    return config;
  }
  function buildSwingConfig(C) {
    const p=C.nominal,m00=C.m00.map((v,i)=>v+p.k*C.m00_k[i]);m00[0]+=p.J;
    return {law:'energy-inverse-v1',energy_gain:7000,center_gain:0,damping_gain:1.5,kick_accel:35,
      speed_target:Math.min(C.arm_no_load_speed,C.arm_speed_lim),capture_angle:5*Math.PI/180,
      capture_pend_rate:.2,capture_arm_rate:4,release_angle:Math.PI/3,
      model:{m00,m01:C.m01.map((v,i)=>v+p.k*C.m01_k[i]),m11:C.m11,g:C.g1.slice(),
        Fp:p.Fp,Fm:p.Fm,b:p.b,arm_fric_eps:C.arm_fric_eps,pend_fl:C.pend_fl*p.pend_fl,
        pend_fl_eps:C.pend_fl_eps,pend_damping:C.pend_damping,pend_c2:C.pend_c2,kt:p.kt}};
  }
  /* Candidate adapted from furuta_platform/swingup.py EnergyTeacher. The
   * current down-zero model has E_dot(input)=-M01*alpha_dot*arm_acceleration;
   * using the sign of the old MATLAB upright-zero torque law would be wrong.
   * Nominal friction is cancelled only within this swing-up law, then the
   * existing actuator path still imposes its speed/current/braking limits. */
  function swingController(C,limit) {
    const s=buildSwingConfig(C),m=s.model,dt=1/C.ctrl_hz;
    if(Math.abs(m.g[0])+Math.abs(m.g[1])>1e-8*Math.abs(m.g[2]))throw Error('Unsupported swing-up gravity coefficients');
    const self={config:s,last:{}};
    self.capture=x=>Math.abs(PS.wrap(x[1]-Math.PI))<=s.capture_angle&&Math.abs(x[3])<=s.capture_pend_rate&&Math.abs(x[2])<=s.capture_arm_rate;
    self.step=function(x){
      if(x.length!==4||!x.every(Number.isFinite))throw Error('Non-finite swing-up state');
      const [theta,a,v,w]=x,ca=Math.cos(a),sa=Math.sin(a),c2=Math.cos(2*a),s2=Math.sin(2*a);
      const d=m.m00,b=m.m01,M00=d[0]+d[1]*ca+d[2]*sa+d[3]*c2+d[4]*s2,M01=b[0]+b[1]*ca+b[2]*sa;
      const d00=-d[1]*sa+d[2]*ca-2*d[3]*s2+2*d[4]*c2,d01=-b[1]*sa+b[2]*ca;
      const inertia=M00-M01*M01/m.m11;
      if(!(inertia>0))throw Error('Invalid swing-up inertia');
      const energy=.5*m.m11*w*w+m.g[2]*(1-ca),target=2*m.g[2],deficit=target-energy;
      let acceleration=-s.energy_gain*deficit*w*M01/m.m11-s.center_gain*theta-s.damping_gain*v;
      if(Math.abs(w)<.05&&ca>.95&&energy<.001){
        const away=-Math.sign(PS.wrap(a))*Math.sign(M01);
        acceleration+=s.kick_accel*(away||1);
      }
      acceleration=clamp(acceleration,(-s.speed_target-v)/dt,(s.speed_target-v)/dt);
      const bias0=d00*v*w+d01*w*w+(v>0?m.Fp:m.Fm)*Math.tanh(v/m.arm_fric_eps)+m.b*v;
      const bias1=-.5*d00*v*v+m.g[0]+m.g[1]*ca+m.g[2]*sa+m.pend_damping*w+m.pend_fl*Math.tanh(w/m.pend_fl_eps)+m.pend_c2*w*Math.abs(w);
      const requested=(inertia*acceleration+bias0-M01/m.m11*bias1)/(m.kt*C.tau_max),u=clamp(requested,-limit,limit);
      if(!Number.isFinite(u)||!Number.isFinite(requested))throw Error('Non-finite swing-up command');
      self.last={requested,u,parts:{},plan:null,qp:null,integral:0,energy,target,deficit,acceleration,phase:'swingup'};
      return u;
    };
    return self;
  }
  /* Separate below-start nonlinear rehearsal. It does not replace the original
   * local balance experiment, and cannot qualify hardware safety by itself. */
  function hybridExperiment(C,raw) {
    const o=options(Object.assign({},raw,{plant:'calibrated',disturbance:0})),ctrl=controller(C,o),swing=swingController(C,o.limit);
    const sim=plant(C,'calibrated').reset(0,0,0,0),rows=[];
    let home=0,phase='swingup',captureTime=null,stopped=false,reason='',sumError=0,sumU=0,maxU=0,sat=0,held=0,longest=0,qpFailures=0;
    const self={o,ctrl,sim,rows,hybrid:true};
    self.tick=function(){
      if(stopped)return false;
      const rawState=[sim.mTh,sim.mAl,sim.mThd,sim.mAld];
      if(phase==='swingup'&&swing.capture(rawState)){phase='balance';home=rawState[0];captureTime=sim.t;}
      const x=[rawState[0]-home,PS.wrap(rawState[1]-Math.PI),rawState[2],rawState[3]];
      if(phase==='balance'&&Math.abs(x[1])>swing.config.release_angle){stopped=true;reason='직립 범위 이탈 · 재스윙업 없이 종료';return false;}
      const u=phase==='swingup'?swing.step(rawState):ctrl.step(x);
      if(phase==='swingup')ctrl.last=swing.last;
      if(ctrl.last.qp&&!ctrl.last.qp.converged){qpFailures++;stopped=true;reason='QP 허용 오차 미도달';return false;}
      advance(sim,u,'calibrated');
      const error=deg(sim.phi());
      if(![sim.th,sim.al,sim.thd,sim.ald,u].every(Number.isFinite)){stopped=true;reason='수치 오류';return false;}
      held=phase==='balance'&&Math.abs(error)<=5&&Math.abs(sim.ald)<=.5?held+sim.ctrlDt:0;longest=Math.max(longest,held);
      sumError+=Math.abs(error);sumU+=u*u;maxU=Math.max(maxU,Math.abs(u));if(Math.abs(ctrl.last.requested)>=o.limit-1e-8)sat++;
      rows.push({t:sim.t,error,arm:deg(sim.th-home),armRate:sim.thd,pendRate:sim.ald,u,tau:sim.tau,requested:ctrl.last.requested,phase});
      if(sim.dead){stopped=true;reason='속도 제한 도달';}
      else if(phase==='balance'&&Math.abs(error)>60){stopped=true;reason='직립 범위 이탈 · 재스윙업 없이 종료';}
      else if(sim.t>=o.seconds-1e-8){stopped=true;reason=captureTime===null?'전환 조건 미도달':'완료';}
      return !stopped;
    };
    self.summary=()=>({method:o.method,plant:o.plant,hybrid:true,startingPose:'hanging',phase,captureTime,status:reason||'진행 중',duration:sim.t,
      meanError:rows.length?sumError/rows.length:0,rmsAction:rows.length?Math.sqrt(sumU/rows.length):0,maxAction:maxU,
      saturation:rows.length?100*sat/rows.length:0,longest,qpFailures,parameters:Object.assign({},o)});
    self.done=()=>stopped;
    return self;
  }
  PS.ControlLab={defaults,options,state,plant,advance,linearize,lqr,mpcSetup,solveQP,controller,experiment,buildHardwareConfig,buildSwingConfig,swingController,hybridExperiment,math:{mm,mv,tr,dot}};
})(window.PS=window.PS||{});
