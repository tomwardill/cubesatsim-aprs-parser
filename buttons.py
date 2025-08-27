from time import sleep

import click
from gpiozero import Button
import paho.mqtt.client as mqtt

import structlog

logging = structlog.get_logger()

action_mqtt_topic = None
action_mqtt_client = None


def reset_button_pressed():
    action_mqtt_client.publish(action_mqtt_topic, "reset")
    logging.info("Reset button pressed, published 'reset' to MQTT")


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
    print(f"Subscribed to topic: {mqtt_topic}")

    # Configure the buttons
    button = Button(17, hold_time=0.2, bounce_time=1.0)
    button.when_pressed = reset_button_pressed

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
