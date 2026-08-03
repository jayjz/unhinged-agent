# 📊 Project Status Report

**Project Name:** Unhinged Agent  
**Current Phase:** Phase 2: Edge Contract & Native Optimization (10 Days to Hardware)  
**Hardware Target:** NVIDIA RTX 4060 (8GB VRAM), 32GB RAM, ESP32-S3-BOX-3B  
**Last Updated:** August 4, 2026  

---

## ✅ Completed Milestones

1. **Architecture Design:** Thin-client asynchronous pipeline separating edge I/O from heavy local inference.
2. **Backend Services & FSM:** Thread-safe Finite State Machine (`IDLE` -> `LISTENING` -> `PROCESSING` -> `SPEAKING`) with active task cancellation for zero-latency barge-in.
3. **ESPHome Bridge Integration:** Replaced raw WebSocket/C++ scaffolding with `aioesphomeapi` to leverage Espressif's battle-tested AEC and WakeNet.
4. **Local LLM Tool-Calling:** Ollama ingesting local GGUF weights (`Qwen 2.5 7B`) fully offloaded to GPU, with structured tool registry.
5. **Native TTS Optimization:** Eliminated HTTP sidecar latency by embedding `kokoro-onnx` + `scipy` resampling directly in the audio pipeline.
6. **Testing & QA Suite:** `pytest` pipelines achieving 100% pass rates, including mocked hardware event stress tests.

---

## 🚧 Next 10-Day Sprint Goals

- **P0-1:** Execute barge-in stress tests on the mocked `esphome_bridge` to validate FSM task cancellation under load.
- **Hardware Delivery:** Awaiting physical delivery of the ESP32-S3-BOX-3B.
- **Immediate Next Step:** Flash physical device with `box3b_unhinged.yaml` and execute end-to-end voice verification on Day 10.