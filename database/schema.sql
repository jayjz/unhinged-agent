# esp32_box_3b.yaml
esphome:
  name: unhinged-agent-node
  friendly_name: Unhinged Agent BOX-3B

esp32:
  board: esp32s3box
  framework:
    type: esp-idf # Required for robust audio and ESP-SR WakeNet [176]

# I2S Audio Configuration for BOX-3B Dual Mics [5]
i2s_audio:
  - id: i2s_in
    i2s_lrclk_pin: GPIO45
    i2s_bclk_pin: GPIO47

microphone:
  - platform: i2s_audio
    id: box_mic
    i2s_din_pin: GPIO46
    adc_type: external
    pdm: false
    channel: stereo
    sample_rate: 16000

# Wake Word (Local) - Keeps device in [IDLE] until triggered
micro_wake_word:
  models:
    - model: hey_jarvis # Placeholder for custom wake word
  on_wake_word_detected:
    - logger.log: "Wake word detected! Transitioning to [LISTENING]"
    - script.execute: start_streaming_to_host