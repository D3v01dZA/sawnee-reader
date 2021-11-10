import logging
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    if (rc != 0):
        logging.error(f"MQTT connection failed with [{rc}]")
        exit(1)
    logging.info("MQTT connected")

def publish(topic):
    client = mqtt.Client()
    client.on_connect = on_connect
    client.connect("mqtt", 1883, 60)
    logging.info(f"Publishing to [{topic}]")
    client.publish(topic)
    client.disconnect()