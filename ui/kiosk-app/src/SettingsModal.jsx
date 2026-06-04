import { useEffect, useState } from 'react'
import { X, Lock, Database, FileText, Trash2, UploadCloud } from 'lucide-react'

function fileNameFromPath(filePath) {
  return filePath.split(/[\\/]/).pop() || filePath
}

export default function SettingsModal({ onClose }) {
  const [isUnlocked, setIsUnlocked] = useState(false)
  const [pin, setPin] = useState('')
  const [pinError, setPinError] = useState(false)
  const [files, setFiles] = useState([])
  const [ingestStatus, setIngestStatus] = useState('')
  const [systemStatus, setSystemStatus] = useState(null)

  const CORRECT_PIN = '1234'

  useEffect(() => {
    if (!isUnlocked || !window.kioskAPI?.getStatus) return
    window.kioskAPI.getStatus()
      .then(setSystemStatus)
      .catch(error => setIngestStatus(error.message || 'Could not load system status.'))
  }, [isUnlocked])

  function handlePinInput(num) {
    if (pin.length < 4) {
      setPin(prev => prev + num)
      setPinError(false)
    }
  }

  function submitPin() {
    if (pin === CORRECT_PIN) {
      setIsUnlocked(true)
      setPin('')
    } else {
      setPinError(true)
      setPin('')
    }
  }

  function handleDeleteFile(id) {
    setFiles(files.filter(file => file.id !== id))
  }

  async function handleUpload() {
    if (!window.kioskAPI?.selectDocuments || !window.kioskAPI?.ingestDocuments) {
      setIngestStatus('Kiosk backend bridge is unavailable. Run the app through Electron.')
      return
    }

    setIngestStatus('Selecting documents...')
    try {
      const selection = await window.kioskAPI.selectDocuments()
      if (selection.canceled) {
        setIngestStatus('')
        return
      }

      setIngestStatus(`Ingesting ${selection.paths.length} document(s) with Docling...`)
      const result = await window.kioskAPI.ingestDocuments(selection.paths)
      const importedFiles = selection.paths.map(filePath => ({
        id: `${filePath}-${Date.now()}`,
        name: fileNameFromPath(filePath),
        size: 'Indexed',
      }))
      setFiles(prev => [...prev, ...importedFiles])
      setIngestStatus(`Ingested ${result.chunkCount} chunks with Docling.`)
    } catch (error) {
      setIngestStatus(error.message || 'Document ingestion failed.')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6 text-white">
      <div className="bg-gray-900 border border-white/10 rounded-3xl w-full max-w-2xl shadow-2xl flex flex-col max-h-full">
        <div className="flex items-center justify-between p-6 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-3 text-xl font-bold">
            {isUnlocked ? <Database className="text-teal-400" /> : <Lock className="text-white/60" />}
            {isUnlocked ? 'System Settings' : 'Admin Login'}
          </div>
          <button
            onClick={onClose}
            className="p-2 text-white/40 hover:text-white rounded-full hover:bg-white/10 transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        <div className="p-8 overflow-y-auto">
          {!isUnlocked ? (
            <div className="max-w-xs mx-auto flex flex-col items-center">
              <p className="text-white/60 mb-6 text-center">Enter 4-digit PIN to access kiosk configurations.</p>

              <div className={`flex gap-3 mb-8 ${pinError ? 'animate-pulse' : ''}`}>
                {[0, 1, 2, 3].map(i => (
                  <div
                    key={i}
                    className={`w-12 h-14 rounded-xl border-2 flex items-center justify-center text-2xl
                      ${pin[i] ? 'border-teal-400 bg-teal-400/10' : 'border-white/20 bg-white/5'}
                      ${pinError ? 'border-red-500 bg-red-500/10' : ''}
                    `}
                  >
                    {pin[i] ? '*' : ''}
                  </div>
                ))}
              </div>

              {pinError && <p className="text-red-400 text-sm mb-4">Incorrect PIN. Try again.</p>}

              <div className="grid grid-cols-3 gap-3 w-full">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                  <button
                    key={num}
                    onClick={() => handlePinInput(num.toString())}
                    className="py-4 bg-white/5 hover:bg-white/10 rounded-xl text-xl font-semibold transition-colors"
                  >
                    {num}
                  </button>
                ))}
                <button
                  onClick={() => { setPin(''); setPinError(false) }}
                  className="py-4 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded-xl font-semibold transition-colors"
                >
                  CLR
                </button>
                <button
                  onClick={() => handlePinInput('0')}
                  className="py-4 bg-white/5 hover:bg-white/10 rounded-xl text-xl font-semibold transition-colors"
                >
                  0
                </button>
                <button
                  onClick={submitPin}
                  disabled={pin.length < 4}
                  className="py-4 bg-teal-500 text-white hover:bg-teal-400 disabled:opacity-50 disabled:hover:bg-teal-500 rounded-xl font-semibold transition-colors"
                >
                  OK
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-8">
              <section>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold">Knowledge Base Directory</h3>
                    <p className="text-sm text-white/50">Documents the AI uses to answer user questions.</p>
                  </div>

                  <button
                    onClick={handleUpload}
                    className="flex items-center gap-2 px-4 py-2 bg-teal-500/10 text-teal-400 hover:bg-teal-500/20 rounded-xl font-semibold transition-colors text-sm"
                  >
                    <UploadCloud size={18} />
                    Upload
                  </button>
                </div>

                {ingestStatus && <p className="mb-3 text-sm text-white/50">{ingestStatus}</p>}

                <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                  {files.length === 0 ? (
                    <div className="p-8 text-center text-white/40">
                      No documents added in this session.
                    </div>
                  ) : (
                    <ul className="divide-y divide-white/10">
                      {files.map(file => (
                        <li key={file.id} className="flex items-center justify-between p-4 hover:bg-white/5 transition-colors">
                          <div className="flex items-center gap-4">
                            <div className="p-2 bg-white/10 rounded-lg text-white/70">
                              <FileText size={20} />
                            </div>
                            <div>
                              <p className="font-medium text-sm text-white/90">{file.name}</p>
                              <p className="text-xs text-white/40">{file.size}</p>
                            </div>
                          </div>
                          <button
                            onClick={() => handleDeleteFile(file.id)}
                            className="p-2 text-white/30 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                            title="Remove from this list"
                          >
                            <Trash2 size={18} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>

              <hr className="border-white/10" />

              <section>
                <h3 className="text-lg font-semibold mb-4">Hardware Diagnostics</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                    <span className="block text-sm text-white/50 mb-1">Ollama Host</span>
                    <span className="text-teal-400 font-semibold">{systemStatus?.ollama?.host || '---'}</span>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                    <span className="block text-sm text-white/50 mb-1">Active Model</span>
                    <span className="font-semibold">{systemStatus?.ollama?.model || '---'}</span>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                    <span className="block text-sm text-white/50 mb-1">TTS Engine</span>
                    <span className="font-semibold">{systemStatus?.tts?.engine || '---'}</span>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                    <span className="block text-sm text-white/50 mb-1">RAG Index</span>
                    <span className="font-semibold">{systemStatus?.rag?.index_path || '---'}</span>
                  </div>
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
