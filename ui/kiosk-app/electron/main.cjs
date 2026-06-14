const { app, BrowserWindow, dialog, ipcMain } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const projectRoot = path.resolve(__dirname, '../../..')
const pythonPath = process.platform === 'win32'
  ? path.join(projectRoot, 'venv', 'Scripts', 'python.exe')
  : path.join(projectRoot, 'venv', 'bin', 'python')
const pythonExecutable = fs.existsSync(pythonPath) ? pythonPath : 'python'
let activeRecording = null

function parseBridgeOutput(stdout, stderr, code) {
  if (code !== 0) {
    console.error(`[kiosk-ui] UI bridge exited with code ${code}`)
  }
  const lastLine = stdout.trim().split(/\r?\n/).filter(Boolean).pop()
  if (!lastLine) {
    throw new Error(stderr || `UI bridge exited with code ${code}`)
  }
  const payload = JSON.parse(lastLine)
  if (!payload.ok) {
    console.error('[kiosk-ui] UI bridge error:', payload.error)
    throw new Error(payload.error || stderr || 'UI bridge command failed')
  }
  return payload
}

function runBridge(args) {
  return new Promise((resolve, reject) => {
    console.log(`[kiosk-ui] python -m kiosk.ui_bridge ${args.join(' ')}`)
    const child = spawn(pythonExecutable, ['-m', 'kiosk.ui_bridge', ...args], {
      cwd: projectRoot,
      windowsHide: true,
    })
    let stdout = ''
    let stderr = ''

    child.stdout.on('data', chunk => {
      const text = chunk.toString()
      stdout += text
      process.stdout.write(text)
    })
    child.stderr.on('data', chunk => {
      const text = chunk.toString()
      stderr += text
      process.stderr.write(text)
    })
    child.on('error', error => {
      console.error('[kiosk-ui] failed to start UI bridge', error)
      reject(error)
    })
    child.on('close', code => {
      try {
        const payload = parseBridgeOutput(stdout, stderr, code)
        console.log('[kiosk-ui] UI bridge complete')
        resolve(payload)
      } catch (error) {
        console.error('[kiosk-ui] could not parse UI bridge output', error)
        reject(new Error(stderr || error.message))
      }
    })
  })
}

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

ipcMain.handle('kiosk:ask', async (_event, { text, speak = true }) => {
  return runBridge(['ask', '--text', text, speak ? '--speak' : '--no-speak'])
})

ipcMain.handle('kiosk:listen', async (_event, { duration = 5, speak = false }) => {
  return runBridge(['listen', '--duration', String(duration), speak ? '--speak' : '--no-speak'])
})

ipcMain.handle('kiosk:start-recording', async (_event, device) => {
  if (activeRecording) {
    return { ok: true, alreadyRecording: true }
  }

  const args = ['-m', 'kiosk.ui_bridge', 'record-transcribe']
  if (device) {
    args.push('--device', String(device))
    console.log(`[kiosk-ui] python -m kiosk.ui_bridge record-transcribe --device ${device}`)
  } else {
    console.log('[kiosk-ui] python -m kiosk.ui_bridge record-transcribe')
  }

  const child = spawn(pythonExecutable, args, {
    cwd: projectRoot,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  let stdout = ''
  let stderr = ''

  child.stdout.on('data', chunk => {
    const text = chunk.toString()
    stdout += text
    process.stdout.write(text)
  })
  child.stderr.on('data', chunk => {
    const text = chunk.toString()
    stderr += text
    process.stderr.write(text)
  })

  activeRecording = {
    child,
    result: new Promise((resolve, reject) => {
      child.on('error', error => {
        activeRecording = null
        console.error('[kiosk-ui] failed to start recording bridge', error)
        reject(error)
      })
      child.on('close', code => {
        activeRecording = null
        try {
          resolve(parseBridgeOutput(stdout, stderr, code))
        } catch (error) {
          reject(error)
        }
      })
    }),
  }

  return { ok: true }
})

ipcMain.handle('kiosk:stop-recording', async () => {
  if (!activeRecording) {
    throw new Error('Recording has not been started.')
  }
  activeRecording.child.stdin.write('\n')
  activeRecording.child.stdin.end()
  return activeRecording.result
})

ipcMain.handle('kiosk:speak', async (_event, { text }) => {
  return runBridge(['speak', '--text', text])
})

ipcMain.handle('kiosk:select-and-ingest', async () => {
  const result = await selectDocuments()
  if (result.canceled || result.paths.length === 0) {
    return { ok: true, canceled: true, paths: [], chunkCount: 0 }
  }
  return runBridge(['ingest', ...result.paths])
})

async function selectDocuments() {
  const result = await dialog.showOpenDialog({
    title: 'Add knowledge-base documents',
    properties: ['openFile', 'multiSelections'],
    filters: [
      {
        name: 'Documents',
        extensions: ['pdf', 'docx', 'pptx', 'xlsx', 'html', 'htm', 'md', 'csv', 'txt', 'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'webp', 'wav', 'mp3', 'vtt'],
      },
    ],
  })

  if (result.canceled || result.filePaths.length === 0) {
    console.log('[kiosk-ui] document selection canceled')
    return { ok: true, canceled: true, paths: [] }
  }
  console.log(`[kiosk-ui] selected ${result.filePaths.length} document(s)`)
  return { ok: true, canceled: false, paths: result.filePaths }
}

ipcMain.handle('kiosk:select-documents', async () => {
  return selectDocuments()
})

ipcMain.handle('kiosk:ingest', async (_event, { paths }) => {
  if (!Array.isArray(paths) || paths.length === 0) {
    return { ok: true, paths: [], chunkCount: 0 }
  }
  return runBridge(['ingest', ...paths])
})

ipcMain.handle('kiosk:status', async () => {
  return runBridge(['status'])
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
