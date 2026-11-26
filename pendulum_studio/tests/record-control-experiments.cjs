'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ctx={window:{},Math,Float64Array};ctx.PS=ctx.window.PS={};vm.createContext(ctx);
for(const f of ['assets/model.js','js/physics.js','js/control-core.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../src',f),'utf8'),ctx);
const results=[],L=ctx.PS.ControlLab,C=ctx.PS.MODEL;
function run(o){const e=L.experiment(C,o);while(!e.done())e.tick();const s=e.summary();results.push(s);return s;}
for(const plant of ['ideal','calibrated'])for(const method of ['pid','lqr','lmpc'])run({plant,method});
for(const d of [0,1])run({method:'pid',d});
for(const r of [1,10])run({method:'lqr',r});
for(const angle of [5,10,13,20])for(const limit of [.2,.4,.6]){
 const a=run({method:'lmpc',angle,limit,horizon:5}),b=run({method:'lmpc',angle,limit,horizon:30});
 console.log(JSON.stringify({angle,limit,N5:[a.status,+a.meanError.toFixed(3),a.qpFailures],N30:[b.status,+b.meanError.toFixed(3),b.qpFailures]}));
}
fs.writeFileSync(path.join(__dirname,'../design/control_validation/experiments.json'),JSON.stringify({scope:'PC nonlinear simulation, no physical motor',results},null,2));
