'use strict';
const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const ctx={window:{},Math,Number,JSON,Date,TextEncoder}; ctx.PS=ctx.window.PS={wrap:x=>((x+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI}; vm.createContext(ctx);
for(const f of ['blockdefs','block-checks','reward','examples','classroom-core','project']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/js',f+'.js'),'utf8'),ctx);
const P=ctx.PS, V=k=>({t:'get_var',f:{variable:k}}), S=(k,x)=>({t:'set_var',f:{variable:k},a:[x]}), C=(k,x)=>({t:'change_var',f:{variable:k},a:[x]}), add=x=>({t:'plus',a:[x]}), op=(t,a,b)=>({t,a:[a,b]}), index={t:'loop_index'};
function model(nodes,run=[{t:'test',a:[10]}]) {
 const M={B:{},scripts:{reward:[],run:[]},pos:{reward:null,run:null},loose:[],next:1};
 function build(n) { const d=P.DEFS[n.t],b={id:M.next++,type:n.t,s:[],f:{},bodies:[]};M.B[b.id]=b;
  d.tpl.forEach(p=>{if(p.s)b.s.push({block:null,v:p.v===undefined?0:p.v});if(p.dd)b.f[p.dd]=p.opts[0][0];});
  Object.assign(b.f,n.f);(n.a||[]).forEach((a,i)=>{if(typeof a==='number')b.s[i].v=a;else b.s[i].block=build(a);});
  for(let i=0;i<(d.bodies||0);i++)b.bodies.push(((n.body||[])[i]||[]).map(build)); return b.id;
 }
 M.scripts.reward=nodes.map(build);M.scripts.run=run.map(build);return M;
}
function rule(nodes){const r=P.reward.blocks(model(nodes));assert.equal(r.ok,true,JSON.stringify(r.issues));return r;}
function value(r,phi=0,w=0,v=0,u=0,th=0){const e=r.evaluate(phi,w,v,u,th);assert.equal(e.issues.length,0,JSON.stringify(e.issues));return e.value;}
function near(a,b){assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);}
test('variables reset per state and trace has the same final assignments',()=>{
 const r=rule([C('A',{t:'height'}),add(V('A'))]);near(value(r),100);near(value(r),100);near(value(r,Math.PI),0);near(r.trace(0,0,0,0,0).variables.A,100);near(value(r),100);
});
test('count is evaluated once, zero skips, nested indices belong to the closest loop',()=>{
 let r=rule([S('A',3),{t:'repeat',a:[V('A')],body:[[add(index),S('A',0)]]},add(V('A'))]);near(value(r),6);
 r=rule([{t:'repeat',a:[0],body:[[add(999)]]},add(2)]);near(value(r),2);
 r=rule([{t:'repeat',a:[2],body:[[{t:'repeat',a:[3],body:[[add(index)]]},add(index)]]}]);near(value(r),15);
 const tr=r.trace(0,0,0,0,0),keys=Object.keys(tr).filter(k=>k!=='variables');near(keys.reduce((s,k)=>s+tr[k],0),15);
});
test('break and continue inside conditions target the nearest repeat',()=>{
 let r=rule([{t:'repeat',a:[5],body:[[{t:'if',a:[op('eq',index,2)],body:[[{t:'continue_loop'}]]},{t:'if',a:[op('eq',index,4)],body:[[{t:'break_loop'}]]},add(index)]]},add(100)]);near(value(r),104);
 r=rule([{t:'repeat',a:[2],body:[[{t:'repeat',a:[5],body:[[add(1),{t:'break_loop'},add(999)]]},add(index)]]}]);near(value(r),5);
});
test('out-of-loop control and run-domain variables are diagnosed before running',()=>{
 for(const n of [{t:'break_loop'},{t:'continue_loop'},add(index)]) {const m=model([add(1),n]);assert.equal(P.reward.inspect(m).ok,false);}
 const m=model([add(1)],[{t:'cond',f:{key:'gens'},a:[V('A')]},{t:'test',a:[10]}]);assert.equal(P.reward.inspect(m).ok,false);
});
test('invalid fixed/dynamic repeat counts stop with a located error',()=>{
 for(const n of [-1,1.5,21]) {const m=model([{t:'repeat',a:[n],body:[[add(1)]]}]);assert.equal(P.reward.inspect(m).ok,false);}
 const r=rule([S('A',1.5),{t:'repeat',a:[V('A')],body:[[add(1)]]}]);const e=r.evaluate(0,0,0,0,0);assert.equal(e.value,0);assert.ok(e.issues.some(i=>i.code==='repeat-range'&&i.id));
});
test('nested loops cannot exceed the operation budget or freeze trace',()=>{
 let n=add(1);for(let k=0;k<4;k++)n={t:'repeat',a:[20],body:[[n]]};const r=rule([n]);const e=r.evaluate(0,0,0,0,0);assert.equal(e.value,0);assert.ok(e.issues.some(i=>i.code==='execution-budget'));assert.deepEqual(Object.keys(r.trace(0,0,0,0,0)),[]);
});
test('conditional values evaluate only the selected numeric arm',()=>{
 const r=rule([S('A',0),add({t:'choose',a:[{t:'true'},42,op('div',1,V('A'))]})]);near(value(r),42);
 const m=model([add({t:'height'})],[{t:'test',a:[{t:'choose',a:[op('le',1,2),10,3]}]}]);
 assert.equal(P.reward.inspect(m).ok,true);assert.equal(P.reward.runOpts(m).test,10);
});
test('invalid math results are not treated as rewards',()=>{
 const r=rule([S('A',-1),add({t:'math',a:[V('A')],f:{op:'sqrt'}})]);const e=r.evaluate(0,0,0,0,0);assert.equal(e.value,0);assert.ok(e.issues.some(i=>i.code==='calculation-overflow'));
});
test('actual app example blocks match both original reward presets across states',()=>{
 for(const [n,lv] of [[0,1],[1,2]]) {const r=P.reward.blocks(model(P.EXAMPLES[n].nodes)), ref=P.reward.basic(lv,lv);assert.equal(r.ok,true);
  for(let i=0;i<401;i++){const args=[-Math.PI+i/400*2*Math.PI,Math.sin(i)*24,Math.cos(i)*15,Math.sin(i*.7),i*.1];near(value(r,...args),ref.fn(...args));}
 }
});
test('rev22 example matches the documented state terms, excluding transition/terminal penalties',()=>{
 const r=P.reward.blocks(model(P.EXAMPLES[2].nodes));assert.equal(r.ok,true);
 for(let i=0;i<100;i++) {const phi=-Math.PI+i/99*2*Math.PI,w=Math.sin(i)*10,v=Math.cos(i)*14,u=Math.sin(i*.3),arm=i*.6,theta=Math.atan2(Math.sin(arm),Math.cos(arm)),n=Math.exp(-((phi/.15)**2));
  const expected=.5*(1+Math.cos(phi))+n*Math.exp(-w*w)-.02*u*u-.15*Math.max(0,Math.abs(v)-9)**2-.05*n*theta*theta-.2*n*v*v-.05*n*w*w+3*(Math.abs(phi)<=Math.PI/36&&Math.abs(w)<=.5);
  near(value(r,phi,w,v,u,arm),expected);
 }near(value(r),5);
});
test('example loops calculate the stated thresholds',()=>{near(value(P.reward.blocks(model(P.EXAMPLES[3].nodes))),140);near(value(P.reward.blocks(model(P.EXAMPLES[4].nodes))),140);});
test('all examples remain valid and finite, including old examples',()=>{
 for(const ex of P.EXAMPLES){const r=P.reward.blocks(model(ex.nodes));assert.equal(r.ok,true,ex.name+JSON.stringify(r.issues));for(const p of [-Math.PI,-.1,0,.1,Math.PI])assert.ok(Number.isFinite(value(r,p,1,2,.3,.5)));}
});
test('project roundtrip preserves variables/loops, labels do not change policy identity',()=>{
 const M=model(P.EXAMPLES[3].nodes);M.variables={A:'높이 경계',B:'보너스',C:'변수 C',D:'변수 D'};
 const old=P.reward.signature(M),p=P.Project.decode(JSON.stringify({app:'pendulum-studio',v:2,name:'시험',mode:'free',blocks:M})).project;
 const q=P.Project.decode(P.Project.encode(p)).project;assert.equal(q.blocks.variables.A,'높이 경계');assert.equal(P.reward.signature(q.blocks),old);near(value(P.reward.blocks(q.blocks)),140);
 M.variables.A='다른 이름';assert.equal(P.reward.signature(M),old);
 M.variables.B='다른 이름';assert.throws(()=>P.Project.decode(JSON.stringify({app:'pendulum-studio',v:2,name:'시험',mode:'free',blocks:M})),/변수 이름/);
 const legacy=model([add({t:'height'})]);const saved=P.Project.decode(JSON.stringify({app:'pendulum-studio',v:2,name:'옛 작품',mode:'free',blocks:legacy})).project;near(value(P.reward.blocks(saved.blocks)),100);
});


test('debug follows actual branches, loops, variables and cumulative reward',()=>{
 for(const ex of P.EXAMPLES){const r=P.reward.blocks(model(ex.nodes));for(const phi of [-3,-.1,0,.2,3]){const args=[phi,1,2,.3,.4],debug=r.debug(...args);near(debug.value,value(r,...args));assert.equal(debug.issues.length,0);near(debug.events.filter(e=>e.kind==='score').reduce((a,e)=>a+e.value,0),debug.value);if(debug.events.length)near(debug.events.at(-1).total,debug.value);}}
 const r=rule([S('A',0),add({t:'choose',a:[{t:'true'},42,op('div',1,V('A'))]})]);assert.equal(r.debug(0,0,0,0,0).issues.length,0);near(r.debug(0,0,0,0,0).value,42);
 for(let i=0;i<9;i++){const basic=P.reward.basic(Math.floor(i/3),i%3),args=[.4,-2,3,.5];near(basic.debug(...args).value,basic.fn(...args));near(basic.debug(...args).events.at(-1).total,basic.fn(...args));}
});
test('capture metrics include initial hold and failures remain unranked',()=>{
 const m=P.Classroom.metrics(Array.from({length:100},(_,i)=>({t:(i+1)*.02,error:2,velocity:0,u:.5})));near(m.duration,2);near(m.uprightSeconds,2);near(m.captureTime,0);near(m.postCaptureMAE,2);near(m.rmsAction,.5);
 const failed=P.Classroom.metrics([{t:1,error:80,velocity:2,u:.2}]);assert.equal(failed.captureTime,null);assert.equal(failed.postCaptureMAE,null);
 assert.equal(P.Classroom.compare({},{ }).compatible,false);
});
test('v4 mission snapshots roundtrip and v3 migrates without invented lesson records',()=>{
 const p=P.Project.decode(JSON.stringify({app:'pendulum-studio',v:2,name:'수업',mode:'free',blocks:model([add(1)])})).project;
 p.classroom.active='design';p.classroom.missions.design={predict:'조건 하나만 바꾸기',observe:'2회 비교',explain:'이유',runs:[1,2],complete:true};
 const q=P.Project.decode(P.Project.encode(p)).project;assert.equal(q.v,4);assert.equal(q.classroom.missions.design.predict,'조건 하나만 바꾸기');
 p.v=3;delete p.classroom;assert.equal(Object.keys(P.Project.decode(JSON.stringify(p)).project.classroom.missions).length,0);
 const bad=JSON.parse('{"__proto__":{"polluted":true}}');assert.throws(()=>P.Classroom.data(bad));
});
test('grid and bandit snapshot restore resumes the same random sequence',()=>{
 const C=require('../src/js/primer-core.js'),world=C.grid({seed:8});for(let i=0;i<10;i++)world.episode(true);
 const s=world.snapshot(),copy=C.grid(s.opts);copy.restore(s);for(let i=0;i<5;i++)assert.deepEqual(copy.episode(true),world.episode(true));
 const bandit=C.bandit(8);for(let i=0;i<10;i++)bandit.step(.3);const b=bandit.snapshot(),bc=C.bandit(8);bc.restore(b);for(let i=0;i<20;i++)assert.deepEqual(bc.step(.3),bandit.step(.3));
});


test('malformed classroom data fails before any child view can be restored',()=>{
 const C=require('../src/js/primer-core.js'),world=C.grid(),e=world.episode(true),machine=C.bandit(7);
 const s={v:1,grid:world.snapshot(),history:[e],bestEpisode:{episode:e,number:1},selected:0,topic:'grid',futureGamma:.9,banditEpsilon:.3,bandit:machine.snapshot(),answers:[null,null,null]};
 assert.equal(P.Classroom.primer(s).history.length,1);
 assert.throws(()=>P.Classroom.primer({...s,bestEpisode:null}),/최고 기록/);
 assert.throws(()=>P.Classroom.primer({...s,answers:[2,null,null]}),/이해 확인/);
 assert.throws(()=>P.Classroom.primer({...s,selected:1.5}),/정수/);
 const fields={p:'1',i:'0',d:'1',qAngle:'40',qArm:'0.5',r:'1',horizon:'20',angle:'5',limit:'0.8',disturbance:'0',plant:'ideal',startMode:'balance',speed:'1',antiWindup:true};
 const lab={v:1,method:'pid',fields,notes:{},records:[],selected:[]};assert.equal(P.Classroom.control(lab).fields.qAngle,'40');
 assert.throws(()=>P.Classroom.control({...lab,fields:{...fields,limit:'2'}}),/limit/);
 assert.throws(()=>P.Classroom.control({...lab,fields:{...fields,plant:'unsupported'}}),/plant/);
});
