# Unhinged Agent

Local, private, thin-client voice assistant. Edge audio runs on **ESP32-S3-BOX-3B** (ESPHome). Heavy inference stays on the host (RTX 4060 8GB).

**Active branch for hardware prep:** `phase2/p0-hardware-prep`

---

## Architecture

```
ESP32-S3-BOX-3B (ESPHome)
  wake word + mic + speaker + display labels
        |
        |  Native API (aioesphomeapi) — PCM in/out
        v
Host FastAPI
  ESPHomeBridge (no model loads)
  AudioPipeline  — Silero VAD (CPU) + faster-whisper base.en (CUDA) + Kokoro TTS (CPU)
  LLMService     — Ollama tool-calling (GPU via Ollama)
  SQLite notes tools
```

**VRAM rule:** Whisper + Kokoro + Ollama services are constructed **once** in `api/server.py` lifespan and injected into the bridge. Never instantiate `AudioPipelineService` / `LLMService` inside the bridge.

---

## Stack

| Piece | Implementation |
|--------|----------------|
| Edge | ESPHome `box3b_unhinged.yaml` |
| Bridge | `aioesphomeapi` |
| STT | `faster-whisper` `base.en` (default CUDA float16) |
| TTS | `kokoro-onnx` on **CPU** |
| LLM | Ollama local GGUF (`unhinged-qwen` / Modelfile) |
| Memory | SQLite FTS5 notes |

---

## Quickstart (host)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

ollama create unhinged-qwen -f Modelfile

# Optional .env
# ESPHOME_EDGE_IP=192.168.x.x
# STT_DEVICE=cuda          # use cpu only for zero-GPU bring-up tests
# STT_MODEL_SIZE=base.en   # do not raise on 8GB without measuring VRAM

pytest -v
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

Kokoro weights expected at:

- `weights/kokoro-v0_19.onnx`
- `weights/voices.bin`

If missing, STT/LLM still run; TTS returns empty audio.

---

## Edge (when BOX-3B arrives)

1. Edit WiFi in `box3b_unhinged.yaml`.
2. `esphome run box3b_unhinged.yaml`
3. Reserve a static IP; set `ESPHOME_EDGE_IP` in host `.env`.
4. Restart host; confirm `/health` and bridge “Connected” logs.
5. One short wake-word turn; watch `nvidia-smi`.

See `PROJECT_STATUS.md` for the 10-day checklist.

---

## Safety (GPU + edge)

- Do **not** load a second Whisper/LLM in-process.
- Keep STT at `base.en`; keep TTS on CPU.
- Do not remove TTS stream pacing (~30 ms / 1024 bytes) — protects the ESP buffer.
- Prefer a single Ollama model loaded at a time.
