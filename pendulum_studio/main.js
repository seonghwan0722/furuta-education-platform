"use strict";
// Electron main process owns the window, native project file dialogs and real serial ports.
// serialport is optional; without it the simulation and project files still work.
const { app, BrowserWindow, ipcMain, shell, Menu, dialog } = require("electron");
const path = require("path");
const net = require("net");
const fs = require("fs/promises");
const { randomUUID } = require("crypto");
const { pathToFileURL } = require("url");

let SerialPort = null;
let ReadlineParser = null;
try {
  SerialPort = require("serialport").SerialPort;
  ReadlineParser = require("@serialport/parser-readline").ReadlineParser;
} catch (e) {
  SerialPort = null;
}

let win = null;
let port = null;
let portOperation = Promise.resolve();
let projectDialogOpen = false;
const PROJECT_MAX_BYTES = 8 * 1024 * 1024;

function isProjectSender(event) {
  if (!win || win.isDestroyed() || event.sender !== win.webContents ||
      !event.senderFrame || event.senderFrame !== win.webContents.mainFrame) return false;
  try {
    const source = new URL(event.senderFrame.url);
    source.search = "";
    source.hash = "";
    return source.href === pathToFileURL(path.join(__dirname, "src", "index.html")).href;
  } catch (_error) { return false; }
}

function projectFilename(value) {
  let name = path.basename(typeof value === "string" ? value : "");
  name = name.replace(/\.pendulum$/i, "").replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
    .replace(/[. ]+$/g, "").slice(0, 160).trim() || "회전 도립 진자 수업";
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name)) name = "_" + name;
  return name + ".pendulum";
}

async function writeProject(filePath, text) {
  // Write beside the destination, then replace it atomically. A failed write never truncates the old project.
  const temporary = path.join(path.dirname(filePath), ".pendulum-" + randomUUID() + ".tmp");
  let handle = null;
  let created = false;
  try {
    handle = await fs.open(temporary, "wx", 0o600);
    created = true;
    await handle.writeFile(text, "utf8");
    await handle.sync();
    await handle.close();
    handle = null;
    await fs.rename(temporary, filePath);
  } finally {
    if (handle) await handle.close().catch(() => {});
    if (created) await fs.unlink(temporary).catch(() => {});
  }
}

async function readProject(filePath) {
  const handle = await fs.open(filePath, "r");
  try {
    const info = await handle.stat();
    if (!info.isFile()) return { error: "프로젝트 파일을 선택해 주세요." };
    if (info.size > PROJECT_MAX_BYTES) return { error: "프로젝트 파일은 8 MB 이하만 불러올 수 있습니다." };
    // Bound the read as well as checking its initial size, in case another program grows the file.
    const buffer = Buffer.alloc(PROJECT_MAX_BYTES + 1);
    let used = 0;
    while (used < buffer.length) {
      const read = await handle.read(buffer, used, buffer.length - used, used);
      if (!read.bytesRead) break;
      used += read.bytesRead;
    }
    if (used > PROJECT_MAX_BYTES) return { error: "프로젝트 파일은 8 MB 이하만 불러올 수 있습니다." };
    return { canceled: false, name: path.basename(filePath), text: buffer.subarray(0, used).toString("utf8") };
  } finally { await handle.close(); }
}

ipcMain.handle("project:save", async (event, data) => {
  if (!isProjectSender(event)) return { error: "프로젝트는 수업 화면에서 저장해 주세요." };
  if (projectDialogOpen) return { canceled: true };
  if (!data || typeof data.text !== "string" || !data.text.length ||
      Buffer.byteLength(data.text, "utf8") > PROJECT_MAX_BYTES) {
    return { error: "저장할 프로젝트 데이터가 없거나 8 MB를 초과했습니다." };
  }
  projectDialogOpen = true;
  try {
    const picked = await dialog.showSaveDialog(win, {
      title: "수업 프로젝트 저장하기", buttonLabel: "프로젝트 저장",
      defaultPath: path.join(app.getPath("documents"), projectFilename(data.name)),
      filters: [{ name: "Pendulum Studio 수업 프로젝트", extensions: ["pendulum"] }],
      properties: ["createDirectory", "showOverwriteConfirmation"]
    });
    if (picked.canceled || !picked.filePath || !isProjectSender(event)) return { canceled: true };
    const filePath = /\.pendulum$/i.test(picked.filePath) ? picked.filePath : picked.filePath + ".pendulum";
    if (filePath !== picked.filePath) {
      // The native dialog confirmed a different name; confirm the actual destination if it already exists.
      let exists = false;
      try { await fs.stat(filePath); exists = true; } catch (error) { if (error.code !== "ENOENT") throw error; }
      if (exists) {
        const answer = await dialog.showMessageBox(win, {
          type: "question", title: "프로젝트 파일 바꾸기",
          message: path.basename(filePath) + " 파일이 이미 있습니다. 바꿀까요?",
          buttons: ["취소", "바꾸기"], defaultId: 0, cancelId: 0, noLink: true
        });
        if (answer.response !== 1 || !isProjectSender(event)) return { canceled: true };
      }
    }
    await writeProject(filePath, data.text);
    return { canceled: false, name: path.basename(filePath) };
  } catch (_error) {
    return { error: "프로젝트를 저장하지 못했습니다. 저장 위치의 권한과 남은 공간을 확인해 주세요." };
  } finally { projectDialogOpen = false; }
});

ipcMain.handle("project:open", async (event) => {
  if (!isProjectSender(event)) return { error: "프로젝트는 수업 화면에서 불러와 주세요." };
  if (projectDialogOpen) return { canceled: true };
  projectDialogOpen = true;
  try {
    const picked = await dialog.showOpenDialog(win, {
      title: "수업 프로젝트 불러오기", buttonLabel: "프로젝트 불러오기",
      filters: [
        { name: "Pendulum Studio 프로젝트와 이전 작품", extensions: ["pendulum", "json"] },
        { name: "Pendulum Studio 수업 프로젝트", extensions: ["pendulum"] },
        { name: "이전 버전 작품", extensions: ["json"] }
      ],
      properties: ["openFile"]
    });
    if (picked.canceled || !picked.filePaths.length || !isProjectSender(event)) return { canceled: true };
    const filePath = picked.filePaths[0];
    if (!/\.(pendulum|json)$/i.test(filePath)) return { error: ".pendulum 프로젝트 또는 이전 .json 작품을 선택해 주세요." };
    return await readProject(filePath);
  } catch (_error) {
    return { error: "프로젝트 파일을 읽지 못했습니다. 파일이 있는지와 읽기 권한을 확인해 주세요." };
  } finally { projectDialogOpen = false; }
});

/* 개발·시험용 TCP 연결. 키트 프로그램을 --tcp 로 띄우고(가짜 장치 또는 ssh -L 로 끌어온 Pi)
 * PS_KIT_TCP=127.0.0.1:47800 으로 앱을 열면 장치 목록에 나옵니다. 이 PC 안의 주소만 받습니다. */
function devTcp() {
  const m = /^(127\.0\.0\.1|localhost):(\d{2,5})$/.exec(process.env.PS_KIT_TCP || "");
  return m ? { host: "127.0.0.1", port: Number(m[2]), path: "tcp://127.0.0.1:" + m[2] } : null;
}

function openTcp(t) {
  return new Promise((resolve, reject) => {
    const sock = net.createConnection({ host: t.host, port: t.port });
    const connection = { kind: "tcp", handle: sock, ready: false };
    port = connection;
    let buf = "";
    let settled = false;
    const timeout = setTimeout(() => fail(new Error("키트 연결 시간이 초과되었습니다")), 5000);
    function fail(error) {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      if (port === connection) port = null;
      sock.destroy();
      reject(error);
    }
    sock.setEncoding("utf8");
    sock.setNoDelay(true);
    sock.once("connect", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      connection.ready = true;
      resolve(true);
    });
    sock.on("data", (d) => {
      if (port !== connection || !connection.ready) return;
      buf += d;
      if (buf.length > 65536) { send("serial:error", "키트 응답 줄이 너무 깁니다"); closePort().catch(() => {}); return; }
      let i = buf.indexOf("\n");
      while (i >= 0) {
        send("serial:line", buf.slice(0, i).replace(/\r$/, ""));
        buf = buf.slice(i + 1);
        i = buf.indexOf("\n");
      }
    });
    sock.on("close", () => {
      if (!settled) { fail(new Error("키트 연결이 닫혔습니다")); return; }
      if (port !== connection) return;
      port = null;
      send("serial:closed", null);
    });
    sock.on("error", (err) => {
      if (!settled) fail(err);
      else if (port === connection) { send("serial:error", String(err && err.message)); closePort().catch(() => {}); }
    });
  });
}

// Open and close requests must not let a previous port's delayed events affect a new kit.
function queuePortOperation(operation) {
  const result = portOperation.then(operation, operation);
  portOperation = result.catch(() => {});
  return result;
}

function createWindow() {
  win = new BrowserWindow({
    show: process.env.PS_UI_TEST !== "1",
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    backgroundColor: "#E6EDF5",
    title: "Pendulum Studio",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      sandbox: false
    }
  });
  Menu.setApplicationMenu(null);
  win.loadFile(path.join(__dirname, "src", "index.html"));
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

function send(channel, payload) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
}

ipcMain.handle("serial:available", () => Boolean(SerialPort) || Boolean(devTcp()));

ipcMain.handle("serial:list", async () => {
  const t = devTcp();
  const extra = t ? [{ path: t.path, manufacturer: "개발용 TCP 연결", serialNumber: "", vendorId: "", productId: "", pnpId: "", friendlyName: "" }] : [];
  if (!SerialPort) return extra;
  const ports = await SerialPort.list();
  return extra.concat(ports.map((p) => ({
    path: p.path,
    manufacturer: p.manufacturer || "",
    serialNumber: p.serialNumber || "",
    vendorId: p.vendorId || "",
    productId: p.productId || "",
    pnpId: p.pnpId || "",
    friendlyName: p.friendlyName || ""
  })));
});

ipcMain.handle("serial:open", (_e, { path: devPath, baudRate }) => queuePortOperation(async () => {
  await closePort();
  const t = devTcp();
  if (t && devPath === t.path) return openTcp(t);
  if (!SerialPort) throw new Error("serialport 모듈이 설치되지 않았습니다");
  const handle = new SerialPort({ path: devPath, baudRate: baudRate || 115200, autoOpen: false });
  const connection = { kind: "serial", handle, ready: false };
  port = connection;
  handle.on("error", (err) => {
    if (port !== connection || !connection.ready) return;
    send("serial:error", String(err && err.message));
    closePort().catch(() => {});
  });
  handle.on("close", () => {
    if (port !== connection) return;
    port = null;
    send("serial:closed", null);
  });
  try {
    await new Promise((resolve, reject) => {
      let settled = false;
      const timeout = setTimeout(() => {
        settled = true;
        reject(new Error("직렬 포트를 열지 못했습니다. 포트 점유 상태와 USB 연결을 확인하세요"));
      }, 8000);
      handle.open((err) => {
        if (settled) {
          // A Windows driver can complete a timed-out open later. Close only that old handle.
          if (!err && handle.isOpen) handle.close(() => {});
          return;
        }
        settled = true;
        clearTimeout(timeout);
        if (err) reject(err); else resolve();
      });
    });
    connection.ready = true;
    const parser = handle.pipe(new ReadlineParser({ delimiter: "\n" }));
    parser.on("data", (line) => {
      if (port === connection && connection.ready) send("serial:line", String(line).replace(/\r$/, ""));
    });
  } catch (error) {
    if (port === connection) await closePort();
    throw error;
  }
  return true;
}));

async function closePort() {
  if (!port) return;
  const connection = port;
  port = null;
  connection.ready = false;
  if (connection.kind === "tcp") { connection.handle.destroy(); return; }
  if (connection.handle.isOpen) await new Promise((resolve) => {
    const timeout = setTimeout(resolve, 2000);
    connection.handle.close(() => { clearTimeout(timeout); resolve(); });
  });
}

ipcMain.handle("serial:close", () => queuePortOperation(async () => {
  await closePort();
  return true;
}));

ipcMain.handle("serial:write", async (_e, line) => {
  const connection = port;
  if (!connection || !connection.ready) throw new Error("키트 연결이 닫혀 있습니다");
  const data = Array.isArray(line) ? line.join("\n") + "\n" : line + "\n";
  await new Promise((resolve, reject) => {
    connection.handle.write(data, (error) => {
      if (error) { reject(error); return; }
      if (port !== connection) { reject(new Error("키트 연결이 바뀌었습니다")); return; }
      if (connection.kind === "serial") connection.handle.drain((err) => err ? reject(err) : resolve());
      else resolve();
    });
  });
  return true;
});

app.whenReady().then(createWindow);
app.on("window-all-closed", async () => {
  await closePort();
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
