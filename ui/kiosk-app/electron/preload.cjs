// Preload runs in a sandboxed context.
// Expose only what the renderer needs here via contextBridge.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('kioskAPI', {
  platform: process.platform,
  ask: (text, options = {}) => ipcRenderer.invoke('kiosk:ask', { text, ...options }),
  listen: (options = {}) => ipcRenderer.invoke('kiosk:listen', options),
  startRecording: () => ipcRenderer.invoke('kiosk:start-recording'),
  stopRecording: () => ipcRenderer.invoke('kiosk:stop-recording'),
  speak: text => ipcRenderer.invoke('kiosk:speak', { text }),
  selectAndIngestDocuments: () => ipcRenderer.invoke('kiosk:select-and-ingest'),
  selectDocuments: () => ipcRenderer.invoke('kiosk:select-documents'),
  ingestDocuments: paths => ipcRenderer.invoke('kiosk:ingest', { paths }),
  getStatus: () => ipcRenderer.invoke('kiosk:status'),
})
