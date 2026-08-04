# Project Status Report

**Project Name:** Unhinged Agent  
**Current Phase:** Phase 2 — Hardware Prep & Edge Contract  
**Active Branch:** `phase2/p0-hardware-prep` (off `feature/esphome-bridge`)  
**Hardware Target:** NVIDIA RTX 4060 (8GB VRAM), 32GB RAM, ESP32-S3-BOX-3B  
**Last Updated:** August 4, 2026  
**Timeline:** Product arrives ~3 days. ~10 days total until first stable e2e voice demo.

---

## Completed Milestones

1. Thin-client architecture (edge I/O vs host inference).
2. Thread-safe FSM with barge-in cancellation (`IDLE` → `LISTENING` → `PROCESSING` → `SPEAKING`).
3. Native `aioesphomeapi` bridge + `box3b_unhinged.yaml` (wake word, AEC, LVGL state labels).
4. Local Ollama tool-calling LLM + SQLite FTS5 notes tools.
5. Native Kokoro-ONNX TTS on CPU (VRAM reserved for Whisper + LLM).
6. Mocked stress tests for barge-in (`tests/test_esphome_bridge_stress.py`).
7. **VRAM safety:** single shared `AudioPipelineService` + `LLMService` injected into bridge (no double GPU load).

---

## P0 Checklist (No Scope Creep)

### Pre-arrival — DONE on this branch

- [x] FSM hardening (allow-list + `InvalidTransition`)
- [x] Config: `esphome_edge_ip` / `esphome_password`
- [x] Bridge barge-in cancel + safe transitions
- [x] Notes DB creates `database/` on boot
- [x] Docs / CHANGELOG / README Phase 2
- [x] **Inject shared models into bridge (no second Whisper/LLM)**
- [x] Utterance + TTS size caps on bridge
- [x] `repomix-output.xml` removed + gitignored on this branch

### On arrival (Days 4–7)

- [ ] Flash `box3b_unhinged.yaml` (WiFi)
- [ ] Static IP → `ESPHOME_EDGE_IP` in `.env`
- [ ] Host connect + wake events in logs
- [ ] First e2e: wake → STT → LLM → TTS on speaker
- [ ] Watch `nvidia-smi` on first turns

### Stabilization (Days 8–10)

- [ ] Barge-in latency on real hardware
- [ ] AEC / noise levels in YAML
- [ ] Voice notes tools
- [ ] Minimal run docs if anything still missing

**Out of scope until after day-10 demo:** LVGL face images, new tools, model size upgrades, browser mock revival.

---

## Immediate Next Action

1. Local: `git fetch && git checkout phase2/p0-hardware-prep && pytest -v`
2. Confirm Kokoro weights under `weights/` and Ollama model exists.
3. On hardware day: flash → static IP → one short turn → measure VRAM.
