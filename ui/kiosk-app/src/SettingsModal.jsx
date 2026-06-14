import { useState, useRef, useEffect } from 'react'
import { X, Lock, Database, FileText, Trash2, UploadCloud, Mic, Volume2 } from 'lucide-react'

export default function SettingsModal({ onClose, selectedInputDevice, onSelectedInputDeviceChange }) {
  const [isUnlocked, setIsUnlocked] = useState(false)
  const [pin, setPin] = useState('')
  const [pinError, setPinError] = useState(false)

  const [inputDevices, setInputDevices] = useState([])
  const [outputDevices, setOutputDevices] = useState([])
  const [selectedInput, setSelectedInput] = useState(selectedInputDevice || '')
  const [selectedOutput, setSelectedOutput] = useState('')

  const [systemStatus, setSystemStatus] = useState(null)
  const [ingestStatus, setIngestStatus] = useState('')
  const [ingestInProgress, setIngestInProgress] = useState(false)

  const fileInputRef = useRef(null)

  const [files, setFiles] = useState([
    { id: 1, name: 'employee_policy_2026.pdf', size: '2.4 MB' },
    { id: 2, name: 'troubleshooting_process.docx', size: '1.1 MB' },
    { id: 3, name: 'facility_map.pdf', size: '840 KB' },
    { id: 4, name: 'Test.pdf', size: '22 KB' },
  ])

  const CORRECT_PIN = '1234'

  useEffect(() => {
    if (!isUnlocked) return

    async function fetchDevices() {
      // Request permission first, but always enumerate regardless of outcome
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        stream.getTracks().forEach(t => t.stop())
      } catch {
        // Permission denied or not supported — labels may be generic
      }

      try {
        const devices = await navigator.mediaDevices.enumerateDevices()

        const inputs = devices.filter(d => d.kind === 'audioinput')
        const outputs = devices.filter(d => d.kind === 'audiooutput')

        setInputDevices(inputs)
        setOutputDevices(outputs)

        setSelectedInput(prev => prev || selectedInputDevice || inputs[0]?.deviceId || '')
        setSelectedOutput(prev => prev || outputs[0]?.deviceId || '')

        try {
          if (window.kioskAPI?.getStatus) {
            const status = await window.kioskAPI.getStatus()
            setSystemStatus(status)
          }
        } catch (err) {
          console.error('Failed to fetch system status:', err)
        }
      } catch (err) {
        console.error('Failed to enumerate media devices:', err)
      }
    }

    fetchDevices()
    navigator.mediaDevices.addEventListener('devicechange', fetchDevices)
    return () => navigator.mediaDevices.removeEventListener('devicechange', fetchDevices)
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
    setFiles(files.filter(f => f.id !== id))
  }

  async function triggerFileDialog() {
    if (!window.kioskAPI?.selectAndIngestDocuments) {
      setIngestStatus('Ingestion is unavailable in this build.')
      return
    }

    setIngestStatus('Opening document picker...')
    setIngestInProgress(true)

    try {
      const result = await window.kioskAPI.selectAndIngestDocuments()
      if (!result) {
        setIngestStatus('Ingestion failed: no response from backend.')
        return
      }

      if (result.canceled) {
        setIngestStatus('Document selection canceled.')
        return
      }

      if (result.ok) {
        const uploadedFiles = result.paths || []
        setFiles(prev => [
          ...prev,
          ...uploadedFiles.map((path, index) => ({
            id: Date.now() + index,
            name: path.split(/[/\\]/).pop() || path,
            size: '',
          })),
        ])
        setIngestStatus(`Ingested ${result.chunkCount} chunk(s) from ${uploadedFiles.length} file(s).`)
        return
      }

      setIngestStatus(`Ingestion failed: ${result.error || 'Unknown error.'}`)
    } catch (err) {
      setIngestStatus(`Ingestion failed: ${err?.message || err}`)
    } finally {
      setIngestInProgress(false)
    }
  }

  function handleFileSelected(event) {
    const files = event.target.files
    if (!files || files.length === 0) {
      return
    }
    setFiles(prev => [
      ...prev,
      ...Array.from(files).map((file, index) => ({
        id: Date.now() + index,
        name: file.name,
        size: `${(file.size / 1024).toFixed(1)} KB`,
      })),
    ])
    setIngestStatus(`Added ${files.length} local file(s) for later ingestion.`)
  }

  useEffect(() => {
    setSelectedInput(selectedInputDevice || '')
  }, [selectedInputDevice])

  // Helper: produce a readable label for a device even when the browser returns an empty string
  function deviceLabel(device, kind, index) {
    if (device.label) return device.label
    const prefix = kind === 'audioinput' ? 'Microphone' : 'Speaker'
    // Show a short ID fragment so admins can distinguish devices
    return `${prefix} ${index + 1} (…${device.deviceId.slice(-8)})`
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6 text-white">
      <div className="bg-gray-900 border border-white/10 rounded-3xl w-full max-w-2xl shadow-2xl flex flex-col max-h-full">

        <div className="flex items-center justify-between p-6 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-3 text-xl font-bold">
            {isUnlocked ? <Database className="text-teal-400" /> : <Lock className="text-white/60" />}
            {isUnlocked ? 'System Settings' : 'Admin Login'}
          </div>
          <button onClick={onClose} className="p-2 text-white/40 hover:text-white rounded-full hover:bg-white/10 transition-colors">
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
                {/* FIX 1: was onClick={handlePinInput('0')} — called immediately on render */}
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
                <div className="flex flex-col gap-3 mb-4">
                  <div>
                    <h3 className="text-lg font-semibold">Knowledge Base Directory</h3>
                    <p className="text-sm text-white/50">Documents the AI uses to answer user questions.</p>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <input type="file" ref={fileInputRef} onChange={handleFileSelected} className="hidden" accept=".pdf,.doc,.docx,.txt" />
                    <button
                      onClick={triggerFileDialog}
                      disabled={ingestInProgress}
                      className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-colors ${ingestInProgress ? 'bg-white/10 text-white/40 cursor-not-allowed' : 'bg-teal-500/10 text-teal-400 hover:bg-teal-500/20'}`}
                    >
                      <UploadCloud size={18} />
                      {ingestInProgress ? 'Ingesting…' : 'Upload'}
                    </button>
                  </div>
                  {ingestStatus && (
                    <p className="text-sm text-white/60">{ingestStatus}</p>
                  )}
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                  {files.length === 0 ? (
                    <div className="p-8 text-center text-white/40">No documents currently in the knowledge base.</div>
                  ) : (
                    <ul className="divide-y divide-white/10">
                      {files.map(file => (
                        <li key={file.id} className="flex items-center justify-between p-4 hover:bg-white/5 transition-colors">
                          <div className="flex items-center gap-4">
                            <div className="p-2 bg-white/10 rounded-lg text-white/70"><FileText size={20} /></div>
                            <div>
                              <p className="font-medium text-sm text-white/90">{file.name}</p>
                              <p className="text-xs text-white/40">{file.size}</p>
                            </div>
                          </div>
                          <button onClick={() => handleDeleteFile(file.id)} className="p-2 text-white/30 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors">
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
                <h3 className="text-lg font-semibold mb-1">Audio Hardware Settings</h3>
                <p className="text-sm text-white/50 mb-4">Configure default audio inputs and outputs for this kiosk.</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/5 p-4 rounded-xl border border-white/10 flex flex-col gap-2">
                    <label className="text-sm text-white/50 flex items-center gap-2">
                      <Mic size={16} className="text-teal-400" /> Input Device (Microphone)
                    </label>
                    <select
                      value={selectedInput}
                      onChange={e => {
                        const value = e.target.value
                        setSelectedInput(value)
                        onSelectedInputDeviceChange?.(value)
                      }}
                      className="bg-gray-800 text-white rounded-lg p-2 border border-white/10 text-sm focus:outline-none focus:border-teal-400 w-full"
                    >
                      {inputDevices.length === 0
                        ? <option value="">No input devices found</option>
                        : inputDevices.map((d, i) => (
                            <option key={d.deviceId} value={d.deviceId}>
                              {deviceLabel(d, 'audioinput', i)}
                            </option>
                          ))
                      }
                    </select>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/10 flex flex-col gap-2">
                    <label className="text-sm text-white/50 flex items-center gap-2">
                      <Volume2 size={16} className="text-teal-400" /> Output Device (Speakers)
                    </label>
                    <select value={selectedOutput} onChange={e => setSelectedOutput(e.target.value)}
                      className="bg-gray-800 text-white rounded-lg p-2 border border-white/10 text-sm focus:outline-none focus:border-teal-400 w-full">
                      {outputDevices.length === 0
                        ? <option value="">No output devices found</option>
                        : outputDevices.map((d, i) => (
                            <option key={d.deviceId} value={d.deviceId}>
                              {deviceLabel(d, 'audiooutput', i)}
                            </option>
                          ))
                      }
                    </select>
                  </div>
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
