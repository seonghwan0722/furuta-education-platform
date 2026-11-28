'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.RUNTIME_NODE_MODULES + '/playwright');
const root = path.resolve(__dirname, '../src'), out = path.resolve(__dirname, '../design/imu_validation');
fs.mkdirSync(out, {recursive: true});
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.png':'image/png', '.svg':'image/svg+xml'};
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (error, bytes) => {
    if (error) { res.writeHead(404).end(); return; }
    res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'}).end(bytes);
  });
});

function installMock() {
  const lineHandlers = [], closeHandlers = [];
  const mock = window.__imuMock = {status:'ok', roll:2.4, pitch:-1.7, tilt:2.94,
    reply:true, imu1:true, seq:0, commands:[], checkDelay:800};
  const send = (line, delay=5) => setTimeout(() => lineHandlers.forEach(fn => fn(line)), delay);
  mock.emit = line => send(line);
  window.studio = {serial:{
    available:async () => true,
    list:async () => [{path:'COM-IMU-TEST', friendlyName:'MPU-9250 가상 키트'}],
    open:async () => true,
    close:async () => { closeHandlers.forEach(fn => fn()); return true; },
    onLine:fn => lineHandlers.push(fn), onClosed:fn => closeHandlers.push(fn), onError:() => {},
    write:async raw => {
      for (const line of Array.isArray(raw) ? raw : [raw]) {
        mock.commands.push(line);
        if (line === 'H') send('I Furuta 2.2.0 50 2520 v2 fake control1' + (mock.imu1 ? ' imu1' : ''));
        else if (line === 'Q') send('K idle - -');
        else if (line === 'L') send('L NONE');
        else if (line === 'C') send('C OK temp=25 raw=2048 zero=2048', mock.checkDelay);
        else if (line.startsWith('U ') && mock.reply) {
          const data = {request_id:line.slice(2), status:mock.status, fake:true, seq:++mock.seq, message:mock.status === 'unavailable' ? '센서 배선을 확인해 주세요' : ''};
          if (mock.status === 'ok' || mock.status === 'moving') Object.assign(data,
            {roll_deg:mock.roll, pitch_deg:mock.pitch, tilt_deg:mock.tilt, accel_g:1, gyro_dps:mock.status === 'moving' ? 30 : 0});
          send('U ' + JSON.stringify(data));
        }
      }
      return true;
    }
  }};
}

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page = await browser.newPage({viewport:{width:1440,height:1000}}), errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(installMock);
  const panel = page.locator('#devLevelPanel'), state = () => panel.locator('.imu-level').getAttribute('data-state');
  const set = values => page.evaluate(values => Object.assign(window.__imuMock, values), values);
  const waitState = value => panel.locator('.imu-level[data-state="' + value + '"]').waitFor({timeout:8000});
  async function connect() {
    await page.locator('#mConn').click();
    await page.locator('.devcard').first().click();
    await page.locator('#devConnect').click();
    await page.locator('#devConnected').waitFor();
  }
  try {
    await page.goto('http://127.0.0.1:' + server.address().port + '/');
    await connect();
    await panel.locator('.imu-angle-roll').filter({hasText:'2.4'}).waitFor();
    assert.match(await panel.locator('.imu-angle-pitch').innerText(), /[−-]1\.7/);
    assert.match(await panel.locator('.imu-angle-total').innerText(), /2\.9/);
    assert.notEqual(await state(), 'ready');
    assert.match(await panel.locator('.imu-source').innerText(), /가상/);
    assert.equal(await panel.locator('.imu-target').inputValue(), '1');
    await page.screenshot({path:path.join(out,'connection-adjusting-1440.png'),fullPage:true});

    await set({roll:.2, pitch:-.3, tilt:.36});
    await waitState('settling');
    await waitState('ready');
    const commands = await page.evaluate(() => window.__imuMock.commands);
    assert.ok(commands.filter(line => line.startsWith('U ')).length >= 10, 'continuous passive updates');
    assert.equal(commands.some(line => /^[RGBDPC](?: |$)/.test(line)), false, 'connection sends no motor/run/upload/check commands');
    await page.screenshot({path:path.join(out,'connection-level-1440.png'),fullPage:true});

    await set({status:'moving'}); await waitState('moving');
    await set({status:'ok'}); await waitState('settling');
    await set({reply:false}); await waitState('stale');
    assert.doesNotMatch(await panel.locator('.imu-level-status').innerText(), /수평 완료/);
    await set({reply:true, status:'unavailable'}); await waitState('unavailable');
    await set({status:'ok'}); await waitState('settling'); await waitState('ready');

    // The same physical kit and IMU state are passed to the classical-control iframe.
    await page.locator('#devClose').click();
    await page.locator('#mControl').click();
    const frame = page.frameLocator('#controlFrame');
    await frame.locator('#targetKit').click();
    assert.equal(await frame.locator('#controlLevelDisclosure').getAttribute('open'), null, 'classical level guide starts compact');
    await frame.locator('#controlLevelSummary').filter({hasText:'0.4'}).waitFor();
    await page.screenshot({path:path.join(out,'control-level-1440.png'),fullPage:true});
    await frame.locator('#controlLevelSummary').click();
    await frame.locator('#controlLevelPanel .imu-angle-roll').filter({hasText:'0.2'}).waitFor();
    const expandedStop = await frame.locator('#stop').boundingBox();
    assert.ok(expandedStop && expandedStop.y >= 0 && expandedStop.y + expandedStop.height <= 1000,
      'physical kit stop stays visible even while the level details are expanded');
    await frame.locator('#checkKit').click();
    await frame.locator('#controlLevelPanel .imu-level[data-state="paused"]').waitFor({state:'attached'});
    assert.equal(await frame.locator('#controlLevelDisclosure').getAttribute('open'), null, 'busy kit collapses the passive guide');
    await frame.locator('#kitConnection').filter({hasText:'점검 완료'}).waitFor();
    await frame.locator('#controlLevelPanel .imu-level[data-state="settling"]').waitFor({state:'attached'});
    await frame.locator('#controlLevelPanel .imu-level[data-state="ready"]').waitFor({state:'attached',timeout:8000});
    const stopBounds = await frame.locator('#stop').boundingBox();
    assert.ok(stopBounds && stopBounds.y >= 0 && stopBounds.y + stopBounds.height <= 1000,
      'physical kit stop control stays visible while reading the level panel');
    await page.screenshot({path:path.join(out,'control-level-1440.png'),fullPage:true});
    await page.setViewportSize({width:1100,height:720});
    const smallStop = await frame.locator('#stop').boundingBox();
    assert.ok(smallStop && smallStop.y >= 0 && smallStop.y + smallStop.height <= 720,
      'physical kit stop control stays visible at 1100 x 720');
    await page.screenshot({path:path.join(out,'control-level-1100.png'),fullPage:true});
    await frame.locator('#connectKit').click();

    await page.setViewportSize({width:1100,height:720});
    await panel.scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(out,'connection-level-1100.png'),fullPage:true});
    assert.ok(await page.locator('body').evaluate(el => el.scrollWidth <= innerWidth + 1), 'no horizontal overflow');
    assert.equal(await panel.locator('.imu-level-status').getAttribute('role'), 'status');
    assert.ok(await panel.locator('.imu-target').evaluate(el => !!(el.labels && el.labels.length || el.getAttribute('aria-label'))), 'target control is labelled');

    await page.locator('#devDisconnect').click();
    assert.notEqual(await state(), 'ready');
    await set({imu1:false});
    const before = await page.evaluate(() => window.__imuMock.commands.filter(line => line.startsWith('U ')).length);
    await page.locator('#devConnect').click();
    await waitState('unsupported');
    await page.waitForTimeout(600);
    assert.equal(await page.evaluate(() => window.__imuMock.commands.filter(line => line.startsWith('U ')).length), before, 'older receivers are not polled');
    assert.deepEqual(errors, []);
    console.log('PASS IMU UI: first connection, live angles, stationary hold, no automatic motor command, movement/stale/unavailable recovery, classical bridge, paused checks, old receiver, accessibility and 2 viewport sizes');
  } finally {
    await browser.close();
    server.close();
  }
})().catch(error => {console.error(error);process.exitCode=1;server.close();});
