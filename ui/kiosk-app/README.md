# AI Kiosk — Electron + React + Tailwind + Radix UI

## Dev (on your machine)
```bash
npm run dev
```
Opens Vite + Electron together in kiosk mode.

## Build for Raspberry Pi
```bash
npm run build:electron
```
Outputs a `.deb` package in `dist/` — copy to Pi and install.

## Pi setup
```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2

# 2. Install whisper.cpp (for speech input)
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp && make && bash models/download-ggml-model.sh base.en

# 3. Install & run the kiosk app
sudo dpkg -i kiosk-app.deb
```

## Autostart on boot (systemd)
```bash
sudo systemctl enable kiosk-app
sudo systemctl start kiosk-app
```

## Project structure
```
kiosk-app/
├── electron/
│   ├── main.cjs       ← Electron window (kiosk mode, touch events)
│   └── preload.cjs    ← Secure bridge to renderer
├── src/
│   ├── App.jsx        ← Main UI (keyboard, input, AI response)
│   ├── main.jsx       ← React entry + Radix Theme wrapper
│   └── index.css      ← Tailwind + kiosk resets
├── tailwind.config.js
├── vite.config.js
└── package.json
```
