# Unhinged Agent

**Thin-client private voice note assistant.**

Real-time, low-latency, tool-calling local AI voice system. Edge device (ESP32-S3-BOX-3B) handles audio I/O; host (RTX 4060 class) runs the heavy inference. Data stays local.

**Current status (August 2026):** Phase 1 Software PoC + Browser Mock complete. Physical ESP32-S3-BOX-3B hardware ordered and pending delivery. End-to-end hardware validation is the next milestone.

---

## Architecture

```
ESP32-S3-BOX-3B (edge client)
  - Dual mic / speaker / touchscreen face
  - Wake / record / stream raw PCM over WebSocket
          |
          v
FastAPI WebSocket Gateway (host)
  - Thread-safe FSM (IDLE → LISTENING → THINKING → SPEAKING)
  - Instant barge-in / task cancellation
  - Silero VAD → faster-whisper (CUDA) → local Qwen GGUF via Ollama
  - Tool registry + edge-tts → FFmpeg streaming outbound audio
```

Browser mock (`index.html`) currently stands in for the physical device so the full pipeline can be exercised today.

---

## Tech Stack

- **Gateway:** FastAPI + WebSockets
- **State:** Thread-safe Finite State Machine with barge-in
- **STT:** faster-whisper (Base, CUDA)
- **VAD:** Silero VAD
- **LLM:** Ollama + Qwen 9B-class GGUF (RTX 4060 offload) with native tool calling
- **TTS:** edge-tts + FFmpeg workers
- **Testing:** pytest, pytest-asyncio, ruff

---

## Quick Start (Software PoC)

```bash
git clone https://github.com/jayjz/unhinged-agent.git
cd unhinged-agent

python -m venv venv
# Windows: venv\Scripts\Activate.ps1
source venv/bin/activate

pip install -r requirements.txt

# Create the local model (Ollama must be running)
ollama create unhinged-qwen -f Modelfile

# Tests
pytest -v

# Server
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

Open the browser mock (`index.html` or the served path) to exercise mic streaming, state face, and barge-in.

---

## Completed (Phase 1)

- Thin-client WebSocket architecture design
- FSM with active task cancellation for barge-in
- Full audio pipeline (VAD → STT → LLM → TTS)
- Local tool-calling LLM path on RTX 4060
- Browser digital twin with continuous PCM + canvas state renderer
- pytest + ruff suite (core paths green)

## Blockers / Next

- Await ESP32-S3-BOX-3B delivery
- Port browser WebSocket client logic into ESPHome YAML
- End-to-end voice verification on physical hardware
- Local TTS swap (Kokoro preferred) and basic note memory/tools

See `PROJECT_STATUS.md` for the living status report.

---

## License

MIT
