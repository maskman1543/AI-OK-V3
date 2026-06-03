const { app, BrowserWindow } = require('electron')
const path = require('path')

// Enable touch events for Raspberry Pi touchscreen
app.commandLine.appendSwitch('touch-events', 'enabled')
// Smooth scrolling on Pi display
app.commandLine.appendSwitch('enable-smooth-scrolling')

function createWindow() {
  const win = new BrowserWindow({
    fullscreen: true,
    kiosk: true,          // Locks to fullscreen, hides taskbar
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: '#0f0f0f',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  // Dev: load Vite dev server. Prod: load built files
  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173')
    win.webContents.openDevTools({ mode: 'detach' })
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // Prevent navigation away from the kiosk
  win.webContents.on('will-navigate', (e, url) => {
    if (!url.startsWith('http://localhost')) e.preventDefault()
  })
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
