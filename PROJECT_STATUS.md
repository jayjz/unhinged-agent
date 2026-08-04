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

---

## P0 Checklist (No Scope Creep)

### Pre-arrival (Days 1–3) — DONE / in this branch

- [x] **P0-1 FSM hardening** — Allowed-transition table + `InvalidTransition`. Safe under race conditions.
- [x] **P0-2 Config** — `esphome_edge_ip` / `esphome_password` in Settings; server uses them.
- [x] **P0-3 Bridge** — Explicit cancel on new wake word, safe transitions, empty-buffer → IDLE.
- [x] **P0-4 Notes DB** — `database/` created on first boot.
- [x] **P0-5 Docs** — This status + CHANGELOG updated.

### On arrival (Days 4–7)

- [ ] Flash `box3b_unhinged.yaml` (set WiFi + optional API key).
- [ ] Assign static IP to BOX-3B; set `ESPHOME_EDGE_IP` in `.env`.
- [ ] Confirm host connects (`/health` shows edge_ip) and wake-word events reach the bridge.
- [ ] First end-to-end: wake → STT → LLM → TTS playback on speaker.

### Stabilization (Days 8–10)

- [ ] Measure and tune barge-in latency on real hardware.
- [ ] Confirm AEC / noise suppression levels in YAML.
- [ ] Verify notes tools (`save_note` / `search_notes`) via voice.
- [ ] Document flash + run procedure in README (minimal).

**Out of scope until after day-10 demo:** LVGL face images, new tools, model swaps, browser mock revival, cloud anything.

---

## Immediate Next Action

1. Keep host running with correct `.env` (`ESPHOME_EDGE_IP`).
2. When BOX-3B arrives: flash YAML → static IP → verify connection logs → speak.
