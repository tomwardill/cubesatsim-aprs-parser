import json
from time import sleep

import click
from gpiozero import Button, LED
import paho.mqtt.client as mqtt

import structlog

logging = structlog.get_logger()

action_mqtt_topic = None
action_mqtt_client = None

reset_led = LED(24)
telem_led = LED(6)
sstv_led = LED(5)

aprs_mode_requested = False
sstv_mode_requested = False


def reset_button_pressed():
    reset_led.on()
    action_mqtt_client.publish(action_mqtt_topic, json.dumps({"action": "reset"}))
    logging.info("Reset button pressed, published 'reset' action to MQTT")
    telem_led.off()
    sstv_led.off()


def reset_button_released():
    logging.info("Reset button released")
    sleep(0.5)
    reset_led.off()


def aprs_button_pressed():
    global aprs_mode_requested, sstv_mode_requested
    action_mqtt_client.publish(action_mqtt_topic, json.dumps({"action": "aprs"}))
    logging.info("APRS button pressed, published 'aprs' action to MQTT")
    aprs_mode_requested = True
    sstv_mode_requested = False
    telem_led.blink(on_time=0.2, off_time=0.2)
    sstv_led.off()

def sstv_button_pressed():
    global aprs_mode_requested, sstv_mode_requested
    action_mqtt_client.publish(action_mqtt_topic, json.dumps({"action": "sstv"}))
    logging.info("SSTV button pressed, published 'sstv' action to MQTT")
    aprs_mode_requested = False
    sstv_mode_requested = True
    sstv_led.blink(on_time=0.2, off_time=0.2)
    telem_led.off()


def on_message(client, userdata, msg):
    global aprs_mode_requested, sstv_mode_requested
    logging.info(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    if msg.topic == "cubesatsim/photos":
        logging.info("Processing photo message...")
        if aprs_mode_requested:
            logging.info("Requesting APRS mode...")
        if sstv_mode_requested:
            logging.info("SSTV mode requested but already active.")
        aprs_mode_requested = False
        sstv_mode_requested = False
        telem_led.on()
        sstv_led.off()
    if msg.topic == "cubesatsim/data":
        logging.info("Processing data message...")
        if aprs_mode_requested:
            logging.info("APRS mode requested but already active.")
        if sstv_mode_requested:
            logging.info("Requesting SSTV mode...")
        aprs_mode_requested = False
        sstv_mode_requested = False
        telem_led.off()
        sstv_led.on()


@click.command()
@click.option("--mqtt_host", default="localhost", help="MQTT broker host")
@click.option("--mqtt_port", default=1883, help="MQTT broker port")
@click.option(
    "--mqtt_topic", default="cubesatsim/actions", help="MQTT topic to publish to"
)
@click.option("--mqtt_username", default=None, help="MQTT username (if required)")
@click.option("--mqtt_password", default=None, help="MQTT password (if required)")
def main(mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password):
    """Connect to the MQTT broker and print connection status."""

    global action_mqtt_topic
    action_mqtt_topic = mqtt_topic
    global action_mqtt_client
    action_mqtt_client = mqtt.Client()
    if mqtt_username and mqtt_password:
        action_mqtt_client.username_pw_set(mqtt_username, mqtt_password)

    try:
        action_mqtt_client.connect(mqtt_host, mqtt_port, 60)
        logging.info(f"Connected to MQTT broker at {mqtt_host}:{mqtt_port}")
    except Exception as e:
        logging.error(f"Failed to connect to MQTT broker: {e}")
        return

    action_mqtt_client.loop_start()

    action_mqtt_client.subscribe(mqtt_topic)
    logging.info(f"Subscribed to topic: {mqtt_topic}")

    action_mqtt_client.subscribe("cubesatsim/photos")
    logging.info("Subscribed to topic: cubesatsim/photos")
    action_mqtt_client.subscribe("cubesatsim/data")
    logging.info("Subscribed to topic: cubesatsim/data")

    action_mqtt_client.on_message = on_message

    # Configure the buttons
    button = Button(17, hold_time=0.2, bounce_time=0.1)
    button.when_pressed = reset_button_pressed
    button.when_released = reset_button_released

    aprs_button = Button(22, hold_time=0.2, bounce_time=0.1)
    aprs_button.when_pressed = aprs_button_pressed

    sstv_button = Button(27, hold_time=0.2, bounce_time=0.1)
    sstv_button.when_pressed = sstv_button_pressed

    try:
        while True:
            sleep(0.1)  # Keep the script running
    except KeyboardInterrupt:
        logging.info("Disconnecting from MQTT broker...")
        action_mqtt_client.loop_stop()
        action_mqtt_client.disconnect()


if __name__ == "__main__":
    main(auto_envvar_prefix="CUBESATSIM")
    import sys

    sys.exit(0)
