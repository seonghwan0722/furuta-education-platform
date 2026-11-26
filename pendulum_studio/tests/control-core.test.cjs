'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={window:{},Math,Float64Array};ctx.PS=ctx.window.PS={};vm.createContext(ctx);
for(const f of ['assets/model.js','js/physics.js','js/control-core.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../src',f),'utf8'),ctx);
const PS=ctx.PS,L=PS.ControlLab,C=PS.MODEL,M=L.math;
let checks=0;function test(name,fn){fn();checks++;console.log('PASS',name);}
const near=(a,b,t=1e-6)=>assert.ok(Math.abs(a-b)<t,`${a} != ${b}`);
test('Q and R change the computed feedback, not a policy lookup',()=>{
 const a=L.controller(C,{method:'lqr'}),b=L.controller(C,{method:'lqr',r:10});
 assert.ok(Math.abs(a.design.K[1]-b.design.K[1])>.1);
 const {A,B}=a.lm,P=a.design.P,K=a.design.K,Q=[.5,40,.3,1],PA=M.mm(P,A),atpa=M.mm(M.tr(A),PA),btpa=M.mv(M.tr(PA),B);
 for(let i=0;i<4;i++)for(let j=0;j<4;j++)near(P[i][j],atpa[i][j]-btpa[i]*K[j]+(i===j?Q[i]:0),1e-5);
});
test('QP box optimum has correct bounds and KKT signs',()=>{
 const H=[[4,1],[1,2]],f=[-5,3],q=L.solveQP(H,f,.4);
 near(q.u[0],.4);near(q.u[1],-.4);assert.ok(q.converged);
 // Independently enumerate all 2-D box faces; exercise warm starts at corners.
 for(const f of [[-1,-1],[.2,-.7],[5,-2],[-.3,.1]]){
  const lim=.4,candidates=[];
  for(const x of [-lim,lim])candidates.push([x,Math.max(-lim,Math.min(lim,(-f[1]-x)/2))]);
  for(const y of [-lim,lim])candidates.push([Math.max(-lim,Math.min(lim,(-f[0]-y)/4)),y]);
  const interior=[(-2*f[0]+f[1])/7,(f[0]-4*f[1])/7];
  if(interior.every(x=>Math.abs(x)<=lim))candidates.push(interior);
  const cost=u=>.5*(4*u[0]**2+2*u[0]*u[1]+2*u[1]**2)+f[0]*u[0]+f[1]*u[1];
  const expected=Math.min(...candidates.map(cost)),got=L.solveQP(H,f,lim,[lim,-lim]);
  near(cost(got.u),expected,1e-9);assert.ok(got.converged);
 }
});
test('Condensed MPC cost agrees with independent rollout cost differences',()=>{
 const c=L.controller(C,{method:'lqr'}),{A,B}=c.lm,N=5,Q=[.5,40,.3,1],mp=L.mpcSetup(A,B,Q,1,N,c.design.P),x=[.02,.01,0,0],u=[.01,-.02,.03,0,.01];
 const cost=U=>{let z=x.slice(),sum=0;for(let k=0;k<N;k++){z=M.mv(A,z).map((v,i)=>v+B[i]*U[k]);sum+=U[k]*U[k];sum+=k===N-1?M.dot(z,M.mv(c.design.P,z)):z.reduce((s,v,i)=>s+Q[i]*v*v,0);}return sum;};
 const f=M.mv(mp.F,x),expected=M.dot(u,M.mv(mp.H,u))+2*M.dot(f,u);
 near(cost(u)-cost(Array(N).fill(0)),expected,1e-7);
});
test('Unconstrained MPC first move agrees with LQR and exposes predictions',()=>{
 const x=[0,.002,0,0],a=L.controller(C,{method:'lqr',limit:1}),b=L.controller(C,{method:'lmpc',limit:1});
 near(a.step(x),b.step(x),1e-6);assert.equal(b.last.plan.length,21);assert.ok(b.last.qp.converged);
});
test('PID integral accumulates and anti-windup bounds saturation',()=>{
 const a=L.controller(C,{method:'pid',p:0,d:0,i:1,limit:1,antiWindup:false});a.step([0,.01,0,0]);const before=a.last.parts.I;a.step([0,.01,0,0]);assert.ok(Math.abs(a.last.parts.I)>Math.abs(before));
 const b=L.controller(C,{method:'pid',i:3,limit:.05,antiWindup:true});for(let k=0;k<500;k++)b.step([0,.2,0,0]);near(b.last.integral,0);
});
test('All methods actually stabilize the shared nonlinear teaching plant from ±5°',()=>{
 for(const method of ['pid','lqr','lmpc'])for(const angle of [-5,5]){
  const e=L.experiment(C,{method,angle});while(!e.done())e.tick();const s=e.summary();
  assert.equal(s.status,'완료');assert.ok(s.meanError<.2);assert.ok(Math.abs(e.sim.phi())<.002);assert.ok(s.maxAction<=.8+1e-10);assert.equal(s.qpFailures,0);
 }
});
test('Tuning creates observable failures rather than scripted animations',()=>{
 const e=L.experiment(C,{method:'pid',d:0});while(!e.done())e.tick();assert.notEqual(e.summary().status,'완료');
});
test('Calibrated mode preserves original torque path and never mutates shared constants',()=>{
 const before=JSON.stringify(C),a=L.plant(C,'calibrated').reset(0,Math.PI+.02,0,0),b=new PS.Furuta(C).reset(0,Math.PI+.02,0,0);
 for(const u of [.1,-.2,.3]){L.advance(a,u,'calibrated');b.step(u);near(a.al,b.al,1e-12);near(a.tau,b.tau,1e-12);}
 L.experiment(C,{plant:'ideal'}).tick();assert.equal(JSON.stringify(C),before);
});
test('Bad options are rejected, action constraints hold, and stop conditions terminate',()=>{
 assert.throws(()=>L.options({angle:NaN}));assert.throws(()=>L.options({method:'neural'}));
 for(const method of ['pid','lqr','lmpc']){const e=L.experiment(C,{method,angle:30,limit:.05});let n=0;while(!e.done()&&n++<1001)e.tick();assert.ok(e.done());assert.ok(e.rows.every(r=>Number.isFinite(r.error)&&Math.abs(r.u)<=.05+1e-10));}
});
console.log(`${checks} meaningful control checks passed`);
