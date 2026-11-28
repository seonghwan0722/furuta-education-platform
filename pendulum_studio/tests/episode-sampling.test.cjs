'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');

function harness(){
  let now=0,id=0;const timers=new Map(),PS={};
  const ctx=vm.createContext({window:{PS},PS,Math,Float64Array,performance:{now:()=>now},
    setTimeout(fn){timers.set(++id,fn);return id;},clearTimeout(id){timers.delete(id);}});
  for(const file of ['assets/model.js','js/physics.js','js/device.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../src',file),'utf8'),ctx);
  return {PS,timers,advance(ms){now+=ms;const entry=timers.entries().next().value;if(entry){timers.delete(entry[0]);entry[1]();}}};
}
function rollout(gap,speed=1,seconds=1){
  const h=harness(),dev=new h.PS.SimDevice(h.PS.MODEL),samples=[];let done=0,renders=0;
  h.PS.runEpisode(dev,()=>.05,{seconds,speed,onSample:s=>samples.push(s),onTick:()=>renders++,onDone:()=>done++});
  for(let i=0;h.timers.size&&i<1000;i++)h.advance(gap);
  assert.equal(done,1);assert.ok(renders>0);assert.equal(h.timers.size,0);
  return {samples:JSON.parse(JSON.stringify(samples)),renders,dt:dev.ctrlDt};
}
test('every simulation control step is recorded identically at fast, slow and accelerated display rates',()=>{
  const fast=rollout(8),slow=rollout(640),accelerated=rollout(16,20);
  assert.equal(fast.samples.length,50,'record exactly the requested number of control samples');
  assert.deepEqual(slow.samples,fast.samples);assert.deepEqual(accelerated.samples,fast.samples);
  assert.notEqual(fast.renders,slow.renders);
  fast.samples.forEach((s,i)=>assert.ok(Math.abs(s.t-(i+1)*fast.dt)<1e-9));
});
test('a ten-second experiment does not run an extra step due to floating-point accumulation',()=>{
  const run=rollout(16,20,10);assert.equal(run.samples.length,500);assert.ok(Math.abs(run.samples.at(-1).t-10)<1e-9);
});
test('rejecting a sample stops a batched simulation without executing the remaining steps',()=>{
  const h=harness(),dev=new h.PS.SimDevice(h.PS.MODEL);let samples=0,done=0;
  h.PS.runEpisode(dev,()=>.05,{seconds:1,onSample:()=>++samples<3,onDone:()=>done++});
  h.advance(640);assert.equal(samples,3);assert.ok(Math.abs(dev.sim.t-3*dev.ctrlDt)<1e-9);assert.equal(h.timers.size,0);assert.equal(done,0);
});
test('kit telemetry ignores duplicate/out-of-order sample times and a rejected sample sends stop',async()=>{
  const h=harness();let callbacks,stops=0;const times=[];
  const dev={kind:'kit',upload:async()=>{},run(s,c){callbacks=c;},stop(){stops++;}};
  h.PS.runEpisode(dev,null,{onSample:s=>{times.push(s.t);return s.t<.04;}});
  await Promise.resolve();
  for(const t of [0,.02,.02,.01,.04,.06])callbacks.onState({t});
  assert.deepEqual(times,[.02,.04]);assert.equal(stops,1);
});
