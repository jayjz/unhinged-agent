# 🤖 Unhinged Agent

A real-time, low-latency, tool-calling local AI voice assistant engineered with a thin-client architecture. It decouples edge audio input/output from heavy local inference, keeping your data 100% private and executing locally on consumer hardware.

---

## 🏗️ System Architecture


```

+-------------------------------------------------+
|               ESP32-S3-BOX-3B (Client)          |
|  - MicroWakeWord / Audio Streamer / LCD Display |
+------------------------+------------------------+
|
WebSocket (Raw PCM Audio)
|
v
+---------------------------------------------------------------------------------+
|                                FASTAPI WEBSOCKET GATEWAY                        |
|                                                                                 |
|  +-----------------------+    +------------------------+    +----------------+  |
|  |   Ingestion Queue     |    |   FSM State Manager    |    | Audio Pipeline |  |
|  |  (Asyncio / Thread)   |--->| (IDLE/LISTEN/THINK/TALK)|--->| - Silero VAD   |  |
|  +-----------+-----------+    +-----------+------------+    | - Faster-Whisper| |
+--------------|----------------------------|-----------------| - Edge-TTS     |  |
|                            |                 +--------+-------+  |
v                            v                          v          |
+------------------------------+  +-------------------+          +-------------+  |
|      LLM ENGINE (OLLAMA)     |  |   TOOLS REGISTRY  |          | WebSocket   |  |
|  - Qwen 9B GGUF (RTX 4060)   |  | - System Tools    |          | Outbound    |  |
|  - Native Tool Routing       |  | - Time/Date API   |          | PCM Stream  |  |
+------------------------------+  +-------------------+          +-------------+  |

```

---

## 🛠️ Tech Stack

- **Backend Gateway:** FastAPI + WebSockets (Asynchronous event-driven I/O)
- **State Management:** Thread-safe Finite State Machine (FSM) supporting instant barge-in interruption.
- **Speech-to-Text (STT):** `faster-whisper` (Base model offloaded to CUDA).
- **Voice Activity Detection (VAD):** `Silero VAD` (Real-time frame gating).
- **LLM Engine:** Local GGUF (`Qwen 3.5 9B Q4_K_M`) executed via Ollama on an NVIDIA RTX 4060 GPU with native tool-calling.
- **Text-to-Speech (TTS):** `edge-tts` streaming neural audio converted via FFmpeg thread workers.
- **Testing:** `pytest`, `pytest-asyncio`, and `ruff` (PEP-8 linting/formatting).

---

## 🚀 Quickstart Guide

### 1. Clone & Setup Virtual Environment
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

```

### 2. Configure Ollama with Local GGUF

Ensure Ollama is running and compile your local model using the provided `Modelfile`:

```powershell
ollama create unhinged-qwen -f Modelfile

```

### 3. Run the Test Suite

Verify core FSM transitions, tool routing, and mock WebSocket streams:

```powershell
pytest -v

```

### 4. Boot the FastAPI Server

```powershell
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

```

```

#### 2. Populate `PROJECT_STATUS.md`
Copy and paste this content into your newly created `PROJECT_STATUS.md`:

```markdown
# 📊 Project Status Report

**Project Name:** Unhinged Agent  
**Current Phase:** Phase 1 Software PoC & Browser Mock Validation  
**Hardware Target:** NVIDIA RTX 4060 (8GB VRAM), 32GB RAM, ESP32-S3-BOX-3B  
**Last Updated:** August 2, 2026  

---

## ✅ Completed Milestones

1. **Architecture Design:** Designed a thin-client asynchronous WebSocket pipeline separating edge I/O from heavy local inference.
2. **Backend Services & FSM:** Implemented a thread-safe Finite State Machine (`IDLE` -> `LISTENING` -> `THINKING` -> `SPEAKING`) with active task cancellation for zero-latency barge-in support.
3. **Audio Pipeline Integration:** Integrated Silero VAD frame gating, Faster-Whisper transcription, and async Edge-TTS streaming converted via background FFmpeg thread pool workers.
4. **Local LLM Tool-Calling:** Configured Ollama to ingest local GGUF weights (`Qwen 9B`) fully offloaded to the RTX 4060 GPU, complete with a structured time-fetching tool registry.
5. **Browser Mock Digital Twin (`index.html`):** Built a zero-GC JavaScript client featuring continuous PCM mic streaming, an interruptible playback queue via `ScriptProcessorNode`, and a dynamic canvas state renderer ("the face").
6. **Testing & QA Suite:** Established `pytest` and `ruff` formatting pipelines achieving 100% pass rates across core unit and integration test blocks.

---

## 🚧 Current Blockers & Next Steps

- **Hardware Delivery:** Awaiting physical delivery of the ESP32-S3-BOX-3B hardware board from DigiKey.
- **Immediate Next Step:** Once hardware arrives, port the browser WebSocket logic into an ESPHome YAML configuration to flash the physical device and execute end-to-end voice verification.

```

---