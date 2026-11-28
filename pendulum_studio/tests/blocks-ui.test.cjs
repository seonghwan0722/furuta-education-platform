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
    page.on('dialog', dialog => { errors.push('Unexpected dialog: ' + dialog.message()); return dialog.dismiss(); });
    await page.addInitScript(() => {
      window.__files = {saved:null, reads:0, writes:0};
      window.studio = {project:{
        save:async file => { window.__files.saved = file; window.__files.writes++; return {name:file.name}; },
        open:async () => { window.__files.reads++; return window.__files.saved; }
      }};
    });
    await page.goto('http://127.0.0.1:' + server.address().port + '/?mode=free&step=2');
    async function loadExample(name) {
      await page.locator('[data-tab="examples"]').click();
      await page.getByRole('button', {name:name + ' 규칙 불러오기',exact:true}).click();
      await page.locator('[data-pane="blocks"]').waitFor({state:'visible'});
    }
    async function snapshot() {
      const before = await page.evaluate(() => window.__files.writes);
      await page.locator('#mSave').click();
      await page.waitForFunction(n => window.__files.writes > n, before);
      return page.evaluate(() => JSON.parse(window.__files.saved.text));
    }
    await page.locator('[data-tab="examples"]').click();
    assert.equal(await page.locator('.reward-formula').count(), 3);
    assert.match(await page.locator('#examples').innerText(), /종료 벌점/);
    if (out) await page.screenshot({path:path.join(out,'reward-examples-1440.png'),fullPage:true});
    await loadExample('우리 앱의 실제 보상 · 약하게 / 약하게');
    assert.equal(await page.locator('#boardHost .block[data-type="set_var"]').count(), 4);
    assert.match(await page.locator('#boardHost').innerText(), /직립 목표/);
    await page.locator('#rail [data-cat="data"]').click();
    const variable = page.getByRole('textbox',{name:'변수 A 이름',exact:true});
    assert.equal(await variable.inputValue(), '직립 목표');
    await variable.fill('세우기 점수'); await variable.press('Enter');
    assert.match(await page.locator('#boardHost').innerText(), /세우기 점수/);
    await page.locator('#mUndo').click(); assert.equal(await variable.inputValue(),'직립 목표');
    await page.locator('#mRedo').click(); assert.equal(await variable.inputValue(),'세우기 점수');
    await variable.fill('속도 감점'); await variable.press('Enter');
    assert.equal(await variable.inputValue(),'세우기 점수','duplicate name rejected without altering the model');
    const saved = await snapshot(); assert.equal(saved.blocks.variables.A,'세우기 점수');
    if (out) await page.screenshot({path:path.join(out,'real-reward-blocks-1440.png'),fullPage:true});
    await loadExample('변수와 반복 · 높이 구간 보너스');
    assert.equal(await page.locator('#boardHost .block[data-type="repeat"]').count(),1);
    assert.equal(await variable.inputValue(),'높이 경계');
    await page.locator('#mOpen').click();
    await page.waitForFunction(() => window.__files.reads === 1);
    await page.waitForFunction(() => document.querySelector('[data-variable-name="A"]').value === '세우기 점수');
    assert.equal(await page.locator('#boardHost .block[data-type="set_var"]').count(),4);
    const restored = await snapshot(); assert.deepEqual(restored.blocks,saved.blocks);
    // Execute a real physics rollout through the existing learner's score path.
    const score = await page.evaluate(() => {
      const P=window.PS, M=JSON.parse(window.__files.saved.text).blocks, r=P.reward.blocks(M);
      const policy=new P.MLP(P.pickPolicy(r).spec);
      const total=P.learn.score([new P.Furuta(P.MODEL,{})],policy,r,50);
      return {total,error:r.lastError || null,instant:r.fn(0,0,0,0,0)};
    });
    assert.ok(Number.isFinite(score.total)); assert.equal(score.error,null); assert.equal(score.instant,1.5);
    await loadExample('변수와 반복 · 높이 구간 보너스');
    const loops = await snapshot();
    const value = await page.evaluate(() => {
      const r=PS.reward.blocks(JSON.parse(window.__files.saved.text).blocks);
      return {value:r.fn(0,0,0,0,0),vars:r.trace(0,0,0,0,0).variables};
    });
    assert.equal(value.value,140); assert.equal(value.vars.B,40);
    assert.ok(Object.values(loops.blocks.B).some(b=>b.type==='repeat'));
    if (out) await page.screenshot({path:path.join(out,'loop-variables-1440.png'),fullPage:true});
    await page.setViewportSize({width:1280,height:800});
    await page.locator('#rail [data-cat="flow"]').click();
    assert.equal(await page.locator('#palette .palblock[data-type="repeat"]').count(),1);
    const a=await page.locator('#palette').boundingBox(),b=await page.locator('#boardHost').boundingBox();
    assert.ok(a.x+a.width<=b.x+1,'palette and editor occupy separate columns');
    if (out) await page.screenshot({path:path.join(out,'loop-flow-1280.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,flows:['real reward load','rename/undo/redo','duplicate rejection','project save/open','physics reward rollout','nested repeat example','1280px layout'],score}));
  } finally { if(browser) await browser.close(); await new Promise(resolve=>server.close(resolve)); }
})().catch(error=>{console.error(error);process.exitCode=1;});
