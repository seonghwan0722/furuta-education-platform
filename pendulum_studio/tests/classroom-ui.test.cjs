'use strict';
// Headless classroom flow. Uses a memory-backed project dialog; never connects a kit.
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.RUNTIME_NODE_MODULES + '/playwright');
const root = path.resolve(__dirname, '../src');
const out = process.env.BLOCK_SCREENSHOTS;
if (out) fs.mkdirSync(out, {recursive:true});
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (error, bytes) => {
    if (error) { res.writeHead(404).end(); return; }
    const type = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml'}[path.extname(file)];
    res.writeHead(200, {'Content-Type':type || 'application/octet-stream'}).end(bytes);
  });
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const page = await browser.newPage({viewport:{width:1440,height:1000}}), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let acceptNew=false;
    page.on('dialog', dialog => { if(acceptNew&&dialog.type()==='confirm')return dialog.accept();errors.push('Unexpected dialog: ' + dialog.message()); return dialog.dismiss(); });
    await page.addInitScript(() => {
      window.__files = {saved:null, reads:0, writes:0};
      window.studio = {project:{
        save:async file => { window.__files.saved = file; window.__files.writes++; return {name:file.name}; },
        open:async () => { window.__files.reads++; return window.__files.saved; }
      }};
    });
    await page.goto('http://127.0.0.1:'+server.address().port+'/?step=2');
    const save=async()=>{const n=await page.evaluate(()=>__files.writes);await page.locator('#mSave').click();await page.waitForFunction(n=>__files.writes>n,n);return page.evaluate(()=>JSON.parse(__files.saved.text));};
    // Keep editing faster than the save delay: recovery must still be updated.
    const savedDuringInput=await page.evaluate(async()=>{
      const input=document.getElementById('projName');let caught=false;
      for(let i=0;i<15;i++){
        input.value='연속 입력 '+i;input.dispatchEvent(new Event('input',{bubbles:true}));
        await new Promise(resolve=>setTimeout(resolve,120));
        const copy=JSON.parse(localStorage.getItem('pendulum-classroom-autosave-v4')||'null');
        caught=caught||!!copy?.name.startsWith('연속 입력');
      }
      return caught;
    });assert.equal(savedDuringInput,true,'continuous edits must not starve autosave');
    await page.locator('[data-tab="inquiry"]').click();
    await page.locator('#inquiry-phi').fill('90');await page.locator('#inquiry-phi').dispatchEvent('input');
    const expected=await page.evaluate(()=>PS.reward.basic(1,1).fn(Math.PI/2,0,0,0));
    assert.equal(await page.locator('.preview-score').innerText(),expected.toFixed(3));
    await page.getByRole('button',{name:'다음 한 단계',exact:true}).click();assert.match(await page.locator('.trace-detail').innerText(),/직립 목표/);
    if(out)await page.screenshot({path:path.join(out,'inquiry-preview.png')});
    await page.locator('[data-inquiry="mission"]').click();
    await page.getByRole('textbox',{name:'01 예상',exact:true}).fill('같은 정책도 시험마다 독립 기록이 남을 것이다.');
    await page.locator('[data-step="0"]').click();
    const primer=page.frameLocator('#primerFrame');await primer.locator('[data-topic="grid"]').click();await primer.locator('#trainHundred').click();
    await primer.locator('[data-topic="bandit"]').click();await primer.getByRole('button',{name:'직접 선택 A',exact:true}).click();
    await page.locator('[data-step="2"]').click();
    await page.locator('#mControl').click();const lab=page.frameLocator('#controlFrame');await lab.locator('body[data-lesson-ready="true"]').waitFor();await lab.locator('[data-method="lqr"]').click();await lab.locator('#settingsTab').click();
    await lab.locator('#qAngle').fill('50');await lab.locator('#qAngle').dispatchEvent('input');
    await lab.locator('#notesTab').click();await lab.locator('#predict').fill('이 수업의 LQR 예상');
    await lab.locator('#resultsTab').click();await lab.locator('#compare').click();await lab.locator('#compare').waitFor({state:'visible'});await page.waitForFunction(()=>document.getElementById('controlFrame').contentDocument.querySelectorAll('#records tr').length===3);
    await lab.locator('#back').click();await page.locator('#controlDialog').waitFor({state:'hidden'});
    const before=await save();assert.equal(before.v,4);assert.equal(before.classroom.primer.history.length,100);assert.equal(before.classroom.primer.bandit.n[0],1);assert.equal(before.classroom.control.records.length,3);assert.equal(before.classroom.control.fields.qAngle,'50');
    // Speed only the simulation clock; the controller and physics still execute.
    await page.evaluate(()=>{const run=PS.runEpisode;PS.runEpisode=(dev,ctrl,opt)=>run(dev,ctrl,{...opt,speed:dev.kind==='sim'?20:1});});
    await page.locator('#wrote').check();await page.locator('#btnStart').click();await page.waitForFunction(()=>!document.getElementById('btnStart').disabled);const first=await save();assert.equal(first.results.rows.length,1);
    await page.locator('[data-tab="inquiry"]').click();await page.locator('[data-inquiry="compare"]').click();
    assert.equal(await page.getByLabel('비교 실험 A',{exact:true}).isDisabled(),true);
    await page.locator('#btnStart').click();await page.waitForFunction(()=>!document.getElementById('btnStart').disabled);const second=await save();assert.equal(second.results.rows.length,2);assert.deepEqual(second.results.rows[1],first.results.rows[0]);assert.equal(second.results.rows[0].snapshot.learningSource,'SAC 사전 정책');
    await page.locator('[data-tab="inquiry"]').click();await page.locator('[data-inquiry="compare"]').click();assert.match(await page.locator('#inquiry').innerText(),/동일한 시뮬레이션/);
    const choiceA=page.getByLabel('비교 실험 A',{exact:true}),choiceB=page.getByLabel('비교 실험 B',{exact:true});
    assert.notEqual(await choiceA.inputValue(),await choiceB.inputValue());
    const oldA=await choiceA.inputValue(),oldB=await choiceB.inputValue();await choiceA.selectOption(oldB);
    assert.equal(await choiceB.inputValue(),oldA,'choosing the other experiment swaps the comparison pair');
    const log=second.results.rows[0].data;assert.equal(log.t.length,500);assert.ok(Math.abs(log.t.at(-1)-10)<1e-8);
    for(let i=1;i<log.t.length;i++)assert.ok(Math.abs(log.t[i]-log.t[i-1]-.02)<1e-8,'record all 50 Hz samples even at 20x playback');
    if(out)await page.screenshot({path:path.join(out,'inquiry-comparison.png')});
    await page.locator('#mOpen').click();await page.waitForFunction(()=>__files.reads===1);await page.locator('[data-step="0"]').click();assert.equal(await primer.locator('#episodes').innerText(),'100회');
    await page.locator('[data-step="2"]').click();await page.locator('#mControl').click();await lab.locator('body[data-lesson-ready="true"]').waitFor();assert.equal(await lab.locator('#qAngle').inputValue(),'50');assert.equal(await lab.locator('#records tr').count(),3);assert.equal(await lab.locator('#run').isEnabled(),true);await lab.locator('#back').click();await page.locator('#controlDialog').waitFor({state:'hidden'});
    const restored=await save();assert.deepEqual(restored.classroom.primer.grid,second.classroom.primer.grid);assert.deepEqual(restored.classroom.control.records,second.classroom.control.records);
    await page.waitForFunction(()=>{try{return JSON.parse(localStorage.getItem('pendulum-classroom-autosave-v4')).results.rows.length===2;}catch(_){return false;}});
    await page.reload();await page.getByRole('button',{name:'수업 복구',exact:true}).click();await page.locator('.recovery-bar').waitFor({state:'detached'});const recovered=await save();assert.equal(recovered.results.rows.length,2);assert.equal(recovered.classroom.primer.history.length,100);
    await page.setViewportSize({width:1280,height:850});await page.locator('[data-tab="inquiry"]').click();await page.locator('[data-inquiry="preview"]').click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    // Escape is handled by the parent dialog, so exercise it while the child is running.
    await page.locator('#mControl').click();await lab.locator('body[data-lesson-ready="true"]').waitFor();await lab.locator('#resultsTab').click();await lab.locator('#run').click();
    await page.waitForFunction(()=>parseFloat(document.getElementById('controlFrame').contentDocument.getElementById('clock').textContent)>.05);
    await page.locator('#controlDialog').focus();await page.keyboard.press('Escape');await lab.locator('#status').filter({hasText:'진행 중인 실험'}).waitFor();
    assert.equal(await page.locator('#controlDialog').isVisible(),true);assert.equal(await lab.locator('#stop').isEnabled(),true);
    await lab.locator('#stop').click();await lab.locator('#back').click();await page.locator('#controlDialog').waitFor({state:'hidden'});
    const stopped=await save();assert.equal(stopped.classroom.control.records.length,4);assert.equal(stopped.classroom.control.notes.lqr.predict,'이 수업의 LQR 예상');
    acceptNew=true;await page.locator('#mNew').click();acceptNew=false;
    await page.locator('#mControl').click();await lab.locator('body[data-lesson-ready="true"]').waitFor();await lab.locator('[data-method="lqr"]').click();await lab.locator('#notesTab').click();
    assert.equal(await lab.locator('#predict').inputValue(),'','new projects must not inherit another project\'s local notes');
    assert.equal(await lab.locator('#records tr').count(),0);await lab.locator('#back').click();await page.locator('#controlDialog').waitFor({state:'hidden'});
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,flows:['continuous-edit autosave','reward preview/step','mission notes','100 grid episodes + RNG restore','control records persisted after close/reopen','repeat tests immutable with every control sample','distinct comparison selection','v4 file + autosave recovery','1280px layout','Escape during control simulation','new-project note isolation']}));
  } finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
