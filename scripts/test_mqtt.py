#!/usr/bin/env python3
"""Quick test of MQTT snapshot reception inside the coordinator container."""
import paho.mqtt.client as mqtt
import time

msgs = []

def on_message(client, userdata, msg):
    msgs.append((msg.topic, len(msg.payload)))

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
c.on_message = on_message
c.connect("mosquitto", 1883)
c.subscribe("ring/#")
c.loop_start()
print("Listening for 15 seconds...")
time.sleep(15)
c.loop_stop()
c.disconnect()

print(f"Received {len(msgs)} messages in 15s")
snapshot_msgs = [(t, s) for t, s in msgs if "snapshot/image" in t]
other_msgs = [(t, s) for t, s in msgs if "snapshot/image" not in t]
print(f"  Snapshot image messages: {len(snapshot_msgs)}")
print(f"  Other messages: {len(other_msgs)}")
for t, s in snapshot_msgs[:10]:
    print(f"    {t}: {s} bytes")
for t, s in other_msgs[:10]:
    print(f"    {t}: {s} bytes")
