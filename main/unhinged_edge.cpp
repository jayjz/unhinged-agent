#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2s_std.h"
#include "esp_websocket_client.h"
#include "esp_log.h"
#include "cJSON.h"

static const char *TAG = "UNHINGED_EDGE";

// WebSocket Handle
esp_websocket_client_handle_t ws_client;

// I2S Channel Handles (ESP-IDF v5.x API)
i2s_chan_handle_t tx_chan; // Speaker
i2s_chan_handle_t rx_chan; // Dual-Mic

// Hardware Constants for ESP32-S3-BOX-3B
#define SAMPLE_RATE 16000
#define CHUNK_SIZE_BYTES 1024 // 512 samples * 2 bytes (16-bit mono)

// ==========================================
// BARGE-IN: DMA FLUSH LOGIC
// ==========================================
void handle_barge_in() {
    ESP_LOGW(TAG, "Barge-in detected! Halting speaker DMA.");
    // Instantly stops the I2S TX channel, flushing the hardware buffer
    // This prevents the "ghost audio" echo effect [126], [242]
    i2s_channel_disable(tx_chan);
    
    // Clear any local software queues here if implemented
    
    // Re-enable the channel so it's ready for the next [SPEAKING] state
    i2s_channel_enable(tx_chan);
    ESP_LOGI(TAG, "Hardware buffer cleared. Ready for new audio.");
}

// ==========================================
// WEBSOCKET EVENT HANDLER (Host -> ESP32)
// ==========================================
static void websocket_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;
    
    switch (event_id) {
        case WEBSOCKET_EVENT_DATA:
            if (data->op_code == WS_TRANSPORT_OPCODES_TEXT) {
                // 1. Parse JSON State Changes (IDLE, THINKING, INTERRUPT)
                cJSON *json = cJSON_Parse(data->data_ptr);
                if (json != NULL) {
                    cJSON *event = cJSON_GetObjectItemCaseSensitive(json, "event");
                    if (cJSON_IsString(event) && (event->valuestring != NULL)) {
                        
                        if (strcmp(event->valuestring, "INTERRUPT") == 0) {
                            handle_barge_in(); // Instantly kill audio playback
                        } 
                        else if (strcmp(event->valuestring, "STATE_CHANGE") == 0) {
                            cJSON *state = cJSON_GetObjectItemCaseSensitive(json, "state");
                            ESP_LOGI(TAG, "FSM Transition: %s", state->valuestring);
                            // TODO: Dispatch state to LVGL GUI task here [10]
                        }
                    }
                    cJSON_Delete(json);
                }
            } 
            else if (data->op_code == WS_TRANSPORT_OPCODES_BINARY) {
                // 2. Play Audio: [SPEAKING] State
                // Feed raw PCM bytes directly into the I2S TX DMA buffer
                size_t bytes_written = 0;
                i2s_channel_write(tx_chan, data->data_ptr, data->data_len, &bytes_written, portMAX_DELAY);
            }
            break;
            
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WebSocket Connected to Host");
            break;
            
        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "WebSocket Disconnected");
            break;
    }
}

// ==========================================
// MICROPHONE CAPTURE TASK ([LISTENING] State)
// ==========================================
void mic_stream_task(void *pvParameters) {
    uint8_t *rx_buf = (uint8_t *)calloc(1, CHUNK_SIZE_BYTES);
    size_t bytes_read = 0;
    
    ESP_LOGI(TAG, "Starting I2S Microphone Stream Task");
    
    while (1) {
        // Block until exactly 1024 bytes are read from the dual-mic
        if (i2s_channel_read(rx_chan, rx_buf, CHUNK_SIZE_BYTES, &bytes_read, portMAX_DELAY) == ESP_OK) {
            
            // Only stream to the host if the WebSocket is connected
            if (esp_websocket_client_is_connected(ws_client)) {
                esp_websocket_client_send_bin(ws_client, (const char *)rx_buf, bytes_read, portMAX_DELAY);
            }
        }
        
        // Yield to scheduler to prevent task watchdog triggers
        vTaskDelay(pdMS_TO_TICKS(1)); 
    }
    
    free(rx_buf);
    vTaskDelete(NULL);
}

// ==========================================
// SYSTEM ENTRY
// ==========================================
extern "C" void app_main(void) {
    ESP_LOGI(TAG, "Booting Unhinged Agent Edge Node...");
    
    // NOTE: Wi-Fi initialization omitted for brevity. Ensure Wi-Fi is connected before WS init.
    
    // 1. Initialize I2S Hardware [242]
    // (Pin configurations must match the specific ESP32-S3-BOX-3B schematic)
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    i2s_new_channel(&chan_cfg, &tx_chan, &rx_chan);
    
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = (gpio_num_t)47,  // Example BOX-3B Pin
            .ws   = (gpio_num_t)45,  // Example BOX-3B Pin
            .dout = (gpio_num_t)46,  // Speaker out
            .din  = (gpio_num_t)14   // Mic in
        },
    };
    i2s_channel_init_std_mode(tx_chan, &std_cfg);
    i2s_channel_init_std_mode(rx_chan, &std_cfg);
    i2s_channel_enable(tx_chan);
    i2s_channel_enable(rx_chan);

    // 2. Initialize WebSocket Client
    esp_websocket_client_config_t ws_cfg = {};
    ws_cfg.uri = "ws://192.168.1.X:8000/ws/agent"; // Replace with your RTX 4060 host IP
    
    ws_client = esp_websocket_client_init(&ws_cfg);
    esp_websocket_register_events(ws_client, WEBSOCKET_EVENT_ANY, websocket_event_handler, (void *)ws_client);
    esp_websocket_client_start(ws_client);

    // 3. Pin the Mic Task to Core 1 (Leaving Core 0 for Wi-Fi and LVGL) [176]
    xTaskCreatePinnedToCore(mic_stream_task, "mic_stream", 4096, NULL, 5, NULL, 1);
}