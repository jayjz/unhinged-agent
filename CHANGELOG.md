# Changelog
All notable changes to the Unhinged Agent project will be documented in this file.

## [Unreleased] - Phase 2: Edge Contract & Native Optimization

### Added
- `services/esphome_bridge.py`: Native `aioesphomeapi` bridge mapping ESPHome voice events to local FSM.
- `box3b_unhinged.yaml`: Comprehensive ESPHome configuration with LVGL UI scaffolding and ESP-SR wake word.
- Native `kokoro-onnx` CPU inference to preserve RTX 4060 VRAM for LLM/STT.
- `test_esphome_bridge_stress.py`: Automated barge-in simulation.
- `esphome_edge_ip` / `esphome_password` Settings fields (env-overridable).
- Utterance buffer cap and TTS outbound size cap on the bridge.

### Changed
- **BREAKING**: Removed HTTP TTS sidecar dependency. Migrated to native CPU inference within `AudioPipelineService`.
- **BREAKING**: `ESPHomeBridge` requires injected `audio_pipeline` + `llm` (no internal model construction).
- Updated `config/settings.py` to remove `tts_endpoint` and enforce strict Pydantic V2 validation.
- FSM now enforces an explicit allow-list of transitions (`InvalidTransition` on illegal jumps).
- `api/server.py` reads edge IP/password from Settings and injects shared services into the bridge.
- README rewritten for Phase 2 ESPHome path and VRAM rules.

### Fixed
- **Critical:** double load of Whisper/LLM (bridge no longer constructs models — protects 8GB VRAM).
- Resolved `aioesphomeapi` API drift by passing raw `bytes` to `send_voice_assistant_audio`.
- Renamed `test_eshome_bridge.py` to `test_esphome_bridge.py` for CI/CD compliance.
- Replaced heavy `librosa` dependency with lightweight `scipy` for audio resampling.
- Added auto-reconnect logic to `ESPHomeBridge` for hardware-arrival resilience.
- Bridge cancels in-flight processing on new wake-word (true barge-in).
- `notes_db.init_db` creates `database/` directory if missing.
- Illegal FSM transitions are logged and ignored instead of crashing the event loop.
- Removed tracked `repomix-output.xml`; added to `.gitignore`.
