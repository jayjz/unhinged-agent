import asyncio
import json
import os
import sys
import wave

import websockets

SERVER_URI = "ws://localhost:8000/ws/agent"
INPUT_WAV = "test_input.wav"
OUTPUT_WAV = "test_output.wav"

# Global event to signal when the server returns to IDLE
server_idle_event = asyncio.Event()


async def receive_handler(websocket, out_wf):
    """Listens for JSON state changes and incoming TTS audio bytes."""
    try:
        while True:
            message = await websocket.recv()

            if isinstance(message, str):
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "STATE_CHANGE":
                    state = data.get("state")
                    print(f"\n[FSM STATE] 🟢 {state}")
                    if state == "IDLE":
                        server_idle_event.set()
                elif event_type == "TRANSCRIPT":
                    print(f"\n[STT] 📝 Recognized: '{data.get('text')}'")
                elif event_type == "INTERRUPT":
                    print("\n[SYSTEM] 🛑 Barge-in detected! Playback stopped.")
                    server_idle_event.set()  # Consider interrupt a return to ready state for the test
                else:
                    print(f"\n[SERVER JSON] {data}")

            elif isinstance(message, bytes):
                print(f"🔊 Received {len(message)} bytes of audio data...", end="\r")
                out_wf.writeframes(message)

    except websockets.exceptions.ConnectionClosed:
        print("\n[NETWORK] ❌ Server closed the connection.")
    except asyncio.CancelledError:
        print("\n[SYSTEM] Receiver task cancelled.")


async def send_handler(websocket, in_wf):
    """Reads a local WAV file and streams it exactly like the ESP32 would (512 samples per frame)."""
    chunk_size_bytes = 1024
    print(f"[NETWORK] 🎤 Streaming {INPUT_WAV} to server in real-time...")

    try:
        while True:
            data = in_wf.readframes(512)
            if not data:
                print("\n[NETWORK] 🎤 Finished streaming microphone audio.")
                break

            if len(data) < chunk_size_bytes:
                data = data.ljust(chunk_size_bytes, b"\x00")

            await websocket.send(data)
            await asyncio.sleep(0.032)

    except websockets.exceptions.ConnectionClosed:
        pass
    except asyncio.CancelledError:
        pass


async def main():
    if not os.path.exists(INPUT_WAV):
        print(
            f"[ERROR] Could not find {INPUT_WAV}. Please record a 16kHz 16-bit Mono WAV file."
        )
        sys.exit(1)

    in_wf = wave.open(INPUT_WAV, "rb")
    if (
        in_wf.getframerate() != 16000
        or in_wf.getnchannels() != 1
        or in_wf.getsampwidth() != 2
    ):
        print("[ERROR] Input WAV must be strictly 16kHz, 16-bit, Mono PCM.")
        sys.exit(1)

    out_wf = wave.open(OUTPUT_WAV, "wb")
    out_wf.setnchannels(1)
    out_wf.setsampwidth(2)
    out_wf.setframerate(16000)

    print(f"Attempting to connect to {SERVER_URI}...")

    try:
        async with websockets.connect(SERVER_URI) as websocket:
            print("[NETWORK] ✅ Connected successfully.")

            receive_task = asyncio.create_task(receive_handler(websocket, out_wf))
            send_task = asyncio.create_task(send_handler(websocket, in_wf))

            await send_task
            print("[SYSTEM] 🎤 Audio stream finished. Waiting for AI response...")

            # Wait for the explicit IDLE signal or timeout after 15 seconds
            try:
                await asyncio.wait_for(server_idle_event.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                print("\n[SYSTEM] ⚠️ Timeout waiting for server to return to IDLE.")

            # Give the file writer a moment to flush the last bytes
            await asyncio.sleep(0.5)

    except ConnectionRefusedError:
        print(
            f"[ERROR] Connection refused. Is the FastAPI server running on {SERVER_URI}?"
        )
    except KeyboardInterrupt:
        print("\n[SYSTEM] Exiting...")
    finally:
        in_wf.close()
        out_wf.close()
        print(f"[SYSTEM] 💾 TTS response saved to {OUTPUT_WAV}.")


if __name__ == "__main__":
    asyncio.run(main())
