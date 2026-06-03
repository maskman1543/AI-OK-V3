import { useState, useRef } from 'react'
import { Mic } from 'lucide-react'

export default function App() {
  const [input, setInput] = useState('')
  const [showKb, setShowKb] = useState(false)
  const [response, setResponse] = useState('')
  const [isRecording, setIsRecording] = useState(false) // Added for mic state
  const kbRef = useRef(null)

  function onKbChange(val) {
    setInput(val)
  }

  async function handleSubmit() {
    if (!input.trim()) return
    setResponse('Sending to AI...')
    setShowKb(false)

    // Calls local Ollama — update model name as needed
    try {
      const res = await fetch('http://localhost:11434/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'llama3.2',
          prompt: input,
          stream: false,
        }),
      })
      const data = await res.json()
      setResponse(data.response || 'No response.')
    } catch {
      setResponse('⚠️  Could not reach Ollama. Is it running on localhost:11434?')
    }
  }

  function handleClear() {
    setInput('')
    setResponse('')
    kbRef.current?.clearInput()
  }

  // Placeholder for your speech-to-text logic
  function toggleRecording() {
    setIsRecording(!isRecording)
    // Add your Web Speech API logic here
  }

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white">

      {/* ── Header ────────────────────────────────────── */}
      <header className="flex items-center justify-between px-10 py-6 border-b border-white/10">
        <span className="text-kiosk-lg font-bold tracking-tight">AI-OK</span>
        <span className="text-kiosk-sm text-white/40">Offline · Raspberry Pi</span>
      </header>

      {/* ── Main area ─────────────────────────────────── */}
      <main className="flex-1 flex flex-col items-center px-10 py-8 gap-8">
        <div className="flex-1 w-full max-w-3xl flex flex-col justify-end">
          {response ? (
            <div className="bg-white/5 rounded-3xl p-8 text-kiosk-base leading-relaxed overflow-y-auto">
              {response}
            </div>
          ) : (
            <p className="text-kiosk-xl font-semibold text-white/60 mb-auto">
              How can I help you?
            </p>
          )}
        </div>

        {/* Input Row - Anchored at the bottom */}
        <div className="w-full max-w-3xl flex gap-4 shrink-0">
          
          {/* Input Wrapper for relative positioning */}
          <div className="relative flex-1 flex items-center">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Tap to type or speak…"
              className="w-full bg-white/10 border border-white/20 rounded-2xl
                         pl-6 pr-14 py-4 text-kiosk-base placeholder-white/30
                         focus:outline-none focus:ring-2 focus:ring-teal-400"
            />
            
            {/* Mic Button */}
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

          <button onClick={handleSubmit} className="btn-primary">Ask</button>
          <button onClick={handleClear} className="btn-secondary">Clear</button>
        </div>
      </main>
    </div>
  )
}