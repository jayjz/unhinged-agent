# Changelog
All notable changes to the Unhinged Agent project will be documented in this file.

## [Unreleased] - Phase 2: Edge Contract & Native Optimization
### Added
- `services/esphome_bridge.py`: Native `aioesphomeapi` bridge mapping ESPHome voice events to local FSM.
- `box3b_unhinged.yaml`: Comprehensive ESPHome configuration with LVGL UI scaffolding and ESP-SR wake word.
- Native `kokoro-onnx` CPU inference to preserve RTX 4060 VRAM for LLM/STT.
- `test_esphome_bridge_stress.py`: Automated barge-in simulation.

### Changed
- **BREAKING**: Removed HTTP TTS sidecar dependency. Migrated to native CPU inference within `AudioPipelineService`.
- Updated `config/settings.py` to remove `tts_endpoint` and enforce strict Pydantic V2 validation.

### Fixed
- Resolved `aioesphomeapi` API drift by passing raw `bytes` to `send_voice_assistant_audio`.
- Renamed `test_eshome_bridge.py` to `test_esphome_bridge.py` for CI/CD compliance.
- Replaced heavy `librosa` dependency with lightweight `scipy` for audio resampling.
- Added auto-reconnect logic to `ESPHomeBridge` for hardware-arrival resilience.