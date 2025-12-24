const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  exportStart: (payload) => ipcRenderer.invoke('export-start', payload),
  onProgress: (cb) => ipcRenderer.on('export-progress', (e, data) => cb(data)),
  onFinished: (cb) => ipcRenderer.on('export-finished', (e, data) => cb(data)),
  cancelExport: () => ipcRenderer.send('export-cancel')
})