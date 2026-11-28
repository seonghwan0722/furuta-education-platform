'use strict';
const path=require('node:path'),fs=require('node:fs'),os=require('node:os'),assert=require('node:assert/strict');
const {_electron:electron}=require(process.env.RUNTIME_NODE_MODULES+'/playwright');
(async()=>{
 const packaged=process.env.PS_PACKAGED_EXE;
 const userData=fs.mkdtempSync(path.join(os.tmpdir(),'pendulum-ux-test-'));
 const args=(packaged?[]:[path.resolve(__dirname,'..')]).concat('--user-data-dir='+userData);
 const app=await electron.launch({executablePath:packaged||require('electron'),args,env:{...process.env,PS_UI_TEST:'1',PS_KIT_TCP:''}});
 try{
  const page=await app.firstWindow(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text());});
  await page.waitForLoadState('load');
  await page.locator('#mControl').click();
  await page.waitForFunction(()=>document.querySelector('#controlFrame').contentDocument?.querySelector('#lessonTitle')?.textContent.includes('PID'));
  await page.evaluate(()=>document.querySelector('#controlFrame').contentDocument.querySelector('#compare').click());
  await page.waitForFunction(()=>document.querySelector('#controlFrame').contentDocument.querySelector('#status').textContent.includes('세 방법 비교 완료'));
  assert.equal(await page.evaluate(()=>document.querySelector('#controlFrame').contentDocument.querySelectorAll('#records tr').length),3);
  assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isVisible()),false);
  await page.evaluate(()=>document.querySelector('#controlFrame').contentDocument.querySelector('#back').click());
  await page.locator('#runPre').click();await page.waitForTimeout(200);await page.locator('#btnStop').click();
  assert.deepEqual(errors,[]);console.log('PASS '+(packaged?'packaged':'source')+' Electron: hidden launch, 3 controllers, original SAC playback, no renderer errors');
 }finally{
  await app.close();
  const tempRoot=path.resolve(os.tmpdir()),target=path.resolve(userData);
  assert.equal(path.dirname(target),tempRoot);
  assert.ok(path.basename(target).startsWith('pendulum-ux-test-'));
  fs.rmSync(target,{recursive:true,force:true,maxRetries:3,retryDelay:200});
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
