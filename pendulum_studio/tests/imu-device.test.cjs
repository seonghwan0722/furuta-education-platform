'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness(capability = true) {
  let now = 100000, timerId = 0, onLine, onClosed;
  const intervals = new Map(), timeouts = new Map(), writes = [];
  const serial = {
    onLine(fn) { onLine = fn; }, onClosed(fn) { onClosed = fn; }, onError() {},
    async open() { return true; }, async close() { return true; },
    async write(line) {
      writes.push(line);
      if (line === 'H') onLine('I furuta 2.2.0 50 2520 v2 control1' + (capability ? ' imu1' : ''));
      if (line === 'Q') onLine('K idle - -');
      return true;
    }
  };
  class Clock extends Date { static now() { return now; } }
  const context = vm.createContext({ window: { PS: {}, studio: { serial } }, Date: Clock,
    setInterval(fn) { const id = ++timerId; intervals.set(id, fn); return id; },
    clearInterval(id) { intervals.delete(id); },
    setTimeout(fn) { const id = ++timerId; timeouts.set(id, fn); return id; },
    clearTimeout(id) { timeouts.delete(id); }, TextEncoder, console,
    btoa: value => Buffer.from(value, 'binary').toString('base64') });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/js/device.js'), 'utf8'), context);
  const device = new context.window.PS.KitDevice('COM-TEST');
  return { device, writes, intervals, timeouts,
    advance(ms) { now += ms; }, line(value) { onLine(value); }, closed() { onClosed(); },
    reply(overrides = {}, id = device._imuPending?.id) {
      onLine('U ' + JSON.stringify({ request_id: id, status: 'ok', roll_deg: 0.4, pitch_deg: -0.3,
        tilt_deg: 0.5, accel_g: 1, gyro_dps: 0.1, seq: 1, fake: false, ...overrides }));
    }
  };
}
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }

test('connecting starts passive IMU reads only and preserves signed angles', async () => {
  const h = harness(); await h.device.connect(); await flush();
  assert.deepEqual(h.writes.map(x => x.split(' ')[0]), ['H', 'Q', 'U']);
  assert.equal(h.device.info.imu1, true);
  h.reply(); assert.equal(h.device.imu.status, 'ok');
  assert.equal(h.device.imu.pitch_deg, -0.3);
  assert.equal(h.device.imu.tilt_deg, 0.5);
  h.advance(200); h.device._imuTick(); await flush();
  h.reply({ seq: 2, roll_deg: 2, tilt_deg: 2.03 });
  assert.equal(h.device.imu.roll_deg, 2);
  assert.ok(!h.writes.some(x => /^(R|B|G|C|P|D)( |$)/.test(x)));
});

test('one pending read, stale timeout and late replies cannot revive a green reading', async () => {
  const h = harness(); await h.device.connect(); await flush();
  const oldId = h.device._imuPending.id;
  for (let i = 0; i < 6; i++) { h.advance(200); h.device._imuTick(); }
  await flush(); assert.equal(h.writes.filter(x => x.startsWith('U ')).length, 1);
  h.advance(200); h.device._imuTick();
  assert.equal(h.device.imu.status, 'stale');
  assert.equal(h.device.imu.tilt_deg, undefined);
  h.advance(400); h.device._imuTick(); await flush();
  h.reply({ seq: 1 }, oldId); assert.equal(h.device.imu.status, 'stale');
  h.reply({ seq: 2 }); assert.equal(h.device.imu.status, 'ok');
  h.advance(200); h.device._imuTick(); await flush();
  h.reply({ seq: 2 }); assert.equal(h.device.imu.status, 'stale');
});

test('missing, malformed, nonfinite, fake-mismatched and moving samples are not level', async () => {
  const h = harness(); await h.device.connect(); await flush();
  const sampleCases = [
    [{ status: 'unavailable', message: 'MPU-9250 missing' }, 'unavailable'],
    [{ status: 'ok', roll_deg: null }, 'unavailable'],
    [{ status: 'ok', fake: true }, 'unavailable'],
    [{ status: 'ok', tilt_deg: 181 }, 'unavailable'],
    [{ status: 'ok', accel_g: 1.2, seq: 2 }, 'moving'],
    [{ status: 'ok', gyro_dps: 4, seq: 3 }, 'moving'],
    [{ status: 'moving', gyro_dps: 0, seq: 4 }, 'moving'],
    [{ status: 'ok', seq: 5 }, 'ok']
  ];
  for (const [sample, expected] of sampleCases) {
    if (!h.device._imuPending) { h.advance(200); h.device._imuTick(); await flush(); }
    h.reply(sample); assert.equal(h.device.imu.status, expected);
    if (expected === 'unavailable') assert.equal(h.device.imu.roll_deg, undefined);
  }
  h.advance(200); h.device._imuTick(); await flush(); h.line('U broken-json');
  assert.equal(h.device.imu.status, 'unavailable');
  assert.equal(h.device.connected, true, 'optional IMU failure does not close kit connection');
});

test('run, upload and CAN check pause IMU without stale responses overwriting the pause', async () => {
  const h = harness(); await h.device.connect(); await flush(); h.reply();
  h.advance(200); h.device._imuTick(); await flush(); const pendingId = h.device._imuPending.id;
  h.device.run(1, {}); assert.equal(h.device.imu.status, 'paused');
  h.reply({ seq: 2 }, pendingId); assert.equal(h.device.imu.status, 'paused');
  const count = h.writes.filter(x => x.startsWith('U ')).length;
  h.advance(2000); h.device._imuTick(); await flush();
  assert.equal(h.writes.filter(x => x.startsWith('U ')).length, count);
  h.line('R END done 50'); h.device._imuTick(); await flush(); h.reply({ seq: 3 });
  assert.equal(h.device.imu.status, 'ok');
  const check = h.device.check(); await flush(); h.device._imuTick();
  assert.equal(h.device.imu.status, 'paused'); h.line('C OK temp=25 raw=2104 zero=2104');
  await check; assert.equal(h.device._checking, false);
  h.device._uploading = true; h.device._imuTick(); assert.equal(h.device._imuPending, null);
  h.device._uploading = false; h.device._imuTick(); await flush(); h.reply({ seq: 4 });
  assert.equal(h.device.imu.status, 'ok');
});

test('old receivers keep working without unknown U commands', async () => {
  const h = harness(false); await h.device.connect(); await flush();
  assert.equal(h.device.imu.status, 'unsupported'); assert.equal(h.intervals.size, 0);
  h.advance(5000); h.device._imuTick(); await flush();
  assert.deepEqual(h.writes, ['H', 'Q']); assert.equal(h.device.connected, true);
});

test('disconnect/lost connection clear read timers and reconnect accepts new sensor sequence', async () => {
  const h = harness(); await h.device.connect(); await flush(); h.reply({ seq: 100 });
  h.closed(); assert.equal(h.intervals.size, 0); assert.equal(h.device.imu.status, 'disconnected');
  assert.equal(h.device.imu.tilt_deg, undefined);
  await h.device.connect(); await flush(); h.reply({ seq: 1 }); assert.equal(h.device.imu.status, 'ok');
  await h.device.disconnect(); assert.equal(h.intervals.size, 0); assert.equal(h.device.imu.status, 'disconnected');
  assert.equal(h.device.imu.tilt_deg, undefined);
});
