import { useState, useRef } from 'react'
import { Mic, X, Settings } from 'lucide-react'
import Keyboard from 'react-simple-keyboard'
import 'react-simple-keyboard/build/css/index.css'
import SettingsModal from './SettingsModal'

export default function App() {
  const [input, setInput] = useState('')
  const [showKb, setShowKb] = useState(false)
  const [response, setResponse] = useState('')
  const [status, setStatus] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [layoutName, setLayoutName] = useState('default')
  const [showSettings, setShowSettings] = useState(false)

  const kbRef = useRef(null)

  function onKbChange(val) {
    setInput(val)
  }

  function handleInputChange(e) {
    const val = e.target.value
    setInput(val)
    if (kbRef.current) {
      kbRef.current.setInput(val)
    }
  }

  async function handleSubmit() {
    if (!input.trim()) return
    setResponse('Thinking...')
    setStatus('LLM and TTS are running.')
    setShowKb(false)

    try {
      if (!window.kioskAPI?.ask) {
        throw new Error('Kiosk backend bridge is unavailable. Run the app through Electron.')
      }
      const data = await window.kioskAPI.ask(input, { speak: false })
      setResponse(data.answer || 'No response.')
      setStatus(data.runtimes?.total ? `Answer ready in ${data.runtimes.total.toFixed(1)}s. Speaking...` : 'Speaking...')
      if (data.answer && window.kioskAPI?.speak) {
        await window.kioskAPI.speak(data.answer)
        setStatus(data.runtimes?.total ? `Done in ${data.runtimes.total.toFixed(1)}s` : '')
      } else {
        setStatus(data.runtimes?.total ? `Done in ${data.runtimes.total.toFixed(1)}s` : '')
      }
    } catch (error) {
      setResponse(error.message || 'Could not reach the kiosk backend.')
      setStatus('')
    }
  }

  function handleClear() {
    setInput('')
    setResponse('')
    setStatus('')
    if (kbRef.current) {
      kbRef.current.clearInput()
    }
  }

  async function toggleRecording() {
    if (!window.kioskAPI?.startRecording || !window.kioskAPI?.stopRecording) {
      setResponse('Kiosk backend bridge is unavailable. Run the app through Electron.')
      setStatus('')
      return
    }

    try {
      if (!isRecording) {
        setIsRecording(true)
        setShowKb(false)
        setResponse('')
        setStatus('Recording. Press the mic again to stop.')
        await window.kioskAPI.startRecording()
        return
      }

      setIsRecording(false)
      setStatus('Transcribing...')
      const data = await window.kioskAPI.stopRecording()
      setInput(data.transcript || '')
      if (kbRef.current) {
        kbRef.current.setInput(data.transcript || '')
      }
      setResponse('')
      setStatus('Transcript ready. Press Ask to send it.')
    } catch (error) {
      setIsRecording(false)
      setResponse(error.message || 'Voice transcription failed.')
      setStatus('')
    }
  }

  function handleKeyPress(button) {
    if (button === '{enter}') {
      handleSubmit()
    }
    if (button === '{shift}') {
      setLayoutName(layoutName === 'default' ? 'shift' : 'default')
    }
    if (button === '{numbers}') {
      setLayoutName('numbers')
    }
    if (button === '{abc}') {
      setLayoutName('default')
    }
  }

  function openSettings() {
    setShowSettings(true)
    setShowKb(false)
  }

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white overflow-hidden relative">
      <header className="flex items-center justify-between px-10 py-6 border-b border-white/10 shrink-0">
        <span className="text-xl font-bold tracking-tight">AI-OK</span>

        <div className="flex items-center gap-6">
          <span className="text-sm text-white/40 hidden sm:inline">Offline - Raspberry Pi</span>
          <button
            onClick={openSettings}
            className="text-white/40 hover:text-white p-2 rounded-full hover:bg-white/10 transition-colors"
            title="Settings"
          >
            <Settings size={24} />
          </button>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center px-10 py-6 gap-6 overflow-hidden">
        <div className="flex-1 w-full max-w-3xl flex flex-col justify-end overflow-hidden">
          {response ? (
            <div className="bg-white/5 rounded-3xl p-8 text-base leading-relaxed overflow-y-auto">
              <p>{response}</p>
              {status && <p className="mt-4 text-sm text-white/40">{status}</p>}
            </div>
          ) : (
            <p className="text-xl font-semibold text-white/60 mb-auto">
              How can I help you?
            </p>
          )}
        </div>

        <div className="w-full max-w-3xl flex gap-4 shrink-0 pb-2">
          <div className="relative flex-1 flex items-center">
            <input
              value={input}
              onChange={handleInputChange}
              onFocus={() => setShowKb(true)}
              placeholder="Tap to type or speak..."
              className="w-full bg-white/10 border border-white/20 rounded-2xl
                         pl-6 pr-14 py-4 text-base placeholder-white/30
                         focus:outline-none focus:ring-2 focus:ring-teal-400"
            />

            <button
              onClick={toggleRecording}
              title="Speech to text"
              className={`absolute right-3 p-2 rounded-full transition-colors ${
                isRecording
                  ? 'text-red-400 bg-red-400/10'
                  : 'text-white/40 hover:text-white hover:bg-white/10'
              }`}
            >
              <Mic size={20} />
            </button>
          </div>

          <button onClick={handleSubmit} className="px-6 py-4 bg-teal-500 rounded-2xl font-bold hover:bg-teal-400">Ask</button>
          <button onClick={handleClear} className="px-6 py-4 bg-white/10 rounded-2xl font-bold hover:bg-white/20">Clear</button>
        </div>
      </main>

      {showKb && (
        <div className="w-full bg-gray-900 border-t border-white/10 p-6 shadow-2xl animate-in slide-in-from-bottom-10 shrink-0 relative z-10">
          <div className="max-w-6xl mx-auto relative">
            <button
              onClick={() => setShowKb(false)}
              className="absolute -top-14 right-0 p-3 bg-gray-800 rounded-t-xl text-white/60 hover:text-white transition-colors"
            >
              <X size={28} />
            </button>

            <div className="text-black">
              <Keyboard
                keyboardRef={r => (kbRef.current = r)}
                layoutName={layoutName}
                onChange={onKbChange}
                onKeyPress={handleKeyPress}
                layout={{
                  default: [
                    'q w e r t y u i o p',
                    'a s d f g h j k l',
                    '{shift} z x c v b n m {bksp}',
                    '{numbers} {space} {enter}',
                  ],
                  shift: [
                    'Q W E R T Y U I O P',
                    'A S D F G H J K L',
                    '{shift} Z X C V B N M {bksp}',
                    '{numbers} {space} {enter}',
                  ],
                  numbers: [
                    '1 2 3',
                    '4 5 6',
                    '7 8 9',
                    '{abc} 0 {bksp}',
                  ],
                }}
                display={{
                  '{bksp}': 'Back',
                  '{enter}': 'Ask',
                  '{shift}': 'Shift',
                  '{space}': 'Space',
                  '{numbers}': '123',
                  '{abc}': 'ABC',
                }}
              />
            </div>
          </div>
        </div>
      )}

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  )
}
