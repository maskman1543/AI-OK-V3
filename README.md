# AI-OK-V3

## STT to Ollama CLI

Smoke-test Ollama without audio:

```powershell
venv\Scripts\python -m kiosk.dev_tools.stt_to_ollama_cli --text "Maayong buntag, unsa imong matabang karon?"
```

Run Whisper on a saved WAV file, then send the transcript to Ollama:

```powershell
venv\Scripts\python -m kiosk.dev_tools.stt_to_ollama_cli kiosk\data\recordings\cebuano_test.wav
```

Record a new WAV file, transcribe it, then send the transcript to Ollama:

```powershell
venv\Scripts\python -m kiosk.dev_tools.stt_to_ollama_cli --record 5 --output kiosk\data\recordings\manual_test.wav --device 2
```

Push-to-talk from the terminal:

```powershell
venv\Scripts\python -m kiosk.dev_tools.stt_to_ollama_cli --push-to-talk --output kiosk\data\recordings\push_to_talk.wav --device 2
```

Test configured TTS only:

```powershell
venv\Scripts\python -m kiosk.dev_tools.tts_cli --text "Maayong buntag, andam na ko motubag."
```

Install Piper for Windows with the Amy medium voice:

```powershell
powershell -ExecutionPolicy Bypass -File kiosk\dev_tools\setup_piper_windows.ps1
```

Speak an Ollama response after a typed transcript:

```powershell
venv\Scripts\python -m kiosk.dev_tools.stt_to_ollama_cli --text "Maayong buntag, unsa imong matabang karon?" --speak
```

OpenAI Whisper requires `ffmpeg`. If `ffmpeg` is not on PATH, set `stt.ffmpeg_path`
in `kiosk/config.yaml` to the full path of `ffmpeg.exe`.

The default TTS engine is Piper with the `en_US-amy-medium` voice. Run the Piper
setup command once before using `--speak`.

For the future web GUI, import `SttOllamaBridge` from `kiosk.stt_ollama_bridge`
and keep one bridge instance alive while the app is running.
