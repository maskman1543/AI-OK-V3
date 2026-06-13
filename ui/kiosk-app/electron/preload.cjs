// Preload runs in a sandboxed context.
// Expose only what the renderer needs here via contextBridge.
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('kioskAPI', {
  platform: process.platform,
})
