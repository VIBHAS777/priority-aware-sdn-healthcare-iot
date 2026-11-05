import json
import random
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Please install paho-mqtt to run publishers: pip3 install paho-mqtt")
    exit(1)

BROKER = "127.0.0.1"
PORT = 1883

DEVICES = [
    {"id": "ecg-101", "type": "code-blue-alarm", "topic": "hospital/icu/alarms", "value_range": (0, 1)},
    {"id": "spo2-202", "type": "spo2-sensor", "topic": "hospital/ward-a/vitals", "value_range": (92, 99)},
    {"id": "bed-303", "type": "bed-occupancy", "topic": "hospital/ward-b/routine", "value_range": (0, 1)}
]

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"Connected to MQTT broker successfully.")
    else:
        print(f"Failed to connect to MQTT broker, return code {reason_code}")

if __name__ == "__main__":
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        # Fallback for older paho-mqtt versions
        client = mqtt.Client()
        
    client.on_connect = on_connect
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        
        print("Starting medical sensor publishers...")
        while True:
            for device in DEVICES:
                val = random.uniform(*device["value_range"])
                payload = {
                    "device_id": device["id"],
                    "timestamp": time.time(),
                    "reading": round(val, 2),
                    "status": "CRITICAL" if "alarm" in device["type"] else "NORMAL"
                }
                client.publish(device["topic"], json.dumps(payload))
                print(f"Published {device['type']} to {device['topic']}")
            
            # Simulate real-time gap between packets
            time.sleep(1.5)
            
    except ConnectionRefusedError:
        print("Could not connect to broker. Is Mosquitto running via 'docker-compose up -d'?")
    except KeyboardInterrupt:
        print("\nStopping publishers...")
        client.loop_stop()
        client.disconnect()
