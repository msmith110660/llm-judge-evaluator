const { app, BrowserWindow, shell } = require('electron');
const path = require('path');

// ── Security: prevent multiple instances ──────────────────────────────────────
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 700,
    title: 'LLM Judge Evaluator',
    backgroundColor: '#12161C',   // matches the app background to prevent a white flash
    webPreferences: {
      nodeIntegration: false,     // never expose Node.js to renderer
      contextIsolation: true,     // isolate preload from page scripts
      webSecurity: true,
    },
  });

  // Load the evaluator
  win.loadFile('index.html');

  // Clean UI — hide the default Electron/Chromium menu bar
  win.setMenuBarVisibility(false);

  // Open external links in the system browser, not in the app window
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    // macOS: re-create window when dock icon is clicked and no windows are open
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // On macOS it is standard for apps to stay open until explicitly quit
  if (process.platform !== 'darwin') app.quit();
});

app.on('second-instance', () => {
  // If user tries to open a second instance, focus the existing window
  const windows = BrowserWindow.getAllWindows();
  if (windows.length > 0) {
    const win = windows[0];
    if (win.isMinimized()) win.restore();
    win.focus();
  }
});
