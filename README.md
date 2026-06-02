# AI-OK-V3

## STT to Ollama CLI

End-to-end push-to-talk voice test with stage runtimes and TTS playback:

```powershell
venv\Scripts\python -m kiosk.dev_tools.e2e_voice_cli
```

Run without TTS playback:

```powershell
venv\Scripts\python -m kiosk.dev_tools.e2e_voice_cli --no-speak
```

Raspberry Pi 5:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m kiosk.dev_tools.e2e_voice_cli
```

For Raspberry Pi 5, install system audio tools first, for example
`sudo apt install ffmpeg portaudio19-dev alsa-utils`.
The configured Whisper `medium` model may be slow on a Pi 5; use `base` or `small` in `kiosk/config.yaml`
if you need faster local transcription. Keep Ollama running locally, or set `ollama.host` to another machine.

The TTS engine is configured to use Piper on both Windows and Raspberry Pi.
Install the Amy voice at `kiosk/models/piper/voices/en_US-amy-medium.onnx`.
Install the Piper binary at `kiosk/models/piper/bin/piper.exe` on Windows, or
`kiosk/models/piper/bin/piper` on Raspberry Pi. A `piper` executable on PATH also works.

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

Install the Amy medium voice on Raspberry Pi after installing a Linux Piper binary:

```bash
bash kiosk/dev_tools/setup_piper_raspberry_pi.sh
```

Speak an Ollama response after a typed transcript:

```powershell
venv\Scripts\python -m kiosk.dev_tools.stt_to_ollama_cli --text "Maayong buntag, unsa imong matabang karon?" --speak
```

OpenAI Whisper requires `ffmpeg`. If `ffmpeg` is not on PATH, set `stt.ffmpeg_path`
in `kiosk/config.yaml` to the full path of `ffmpeg.exe`.

The default TTS engine is Piper with the `en_US-amy-medium` voice. Run the Piper
setup command once before using `--speak`.

## GUI integration

Use `VoiceAssistantOrchestrator` as the GUI boundary. Create one instance when
the app starts and reuse it for every request so Whisper, Ollama config, and TTS
do not need to be recreated for every button press.

```python
from kiosk.orchestrator import VoiceAssistantOrchestrator

assistant = VoiceAssistantOrchestrator(config_path="kiosk/config.yaml")
```

For a push-to-talk button:

```python
# Button press / mouse down
assistant.start_recording(device=2)

# Button release / mouse up
audio_path = assistant.stop_recording()
result = assistant.process_audio_file(audio_path, speak=True)

transcript_textbox.setText(result.transcript)
answer_textbox.setText(result.answer)
```

For a typed-message GUI:

```python
result = assistant.process_transcript("Can you help me?", speak=True)
answer_textbox.setText(result.answer)
```

The returned `result` includes:

```python
result.transcript
result.answer
result.audio_path
result.audio_stats
result.runtimes
```

Do not run `process_audio_file()` on the GUI main thread. Whisper and Ollama can
take several seconds, especially on Raspberry Pi 5. Run it in a worker thread,
then update the GUI after the worker finishes.

Minimal threaded pattern:

```python
import threading

def on_talk_pressed():
    assistant.start_recording(device=2)

def on_talk_released():
    audio_path = assistant.stop_recording()
    threading.Thread(target=process_audio, args=(audio_path,), daemon=True).start()

def process_audio(audio_path):
    result = assistant.process_audio_file(audio_path, speak=True)
    print(result.transcript)
    print(result.answer)
    print(result.runtimes)
```

The GUI should catch `RecordingError`, `PiperConfigError`, and `RuntimeError`
from `kiosk.orchestrator` and show those messages in the UI.
