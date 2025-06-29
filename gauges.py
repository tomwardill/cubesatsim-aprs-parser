import json

from adafruit_servokit import ServoKit
import paho.mqtt.client as mqtt
import click

number_channels = 16
servos = {
    "MINUS_X_voltage": 2,
    "PLUS_X_voltage": 3,
    "MINUS_Y_voltage": 4,
    "PLUS_Y_voltage": 5,
    "MINUS_Z_voltage": 6,
    "PLUS_Z_voltage": 7,
}

pca = ServoKit(channels=number_channels)


def scale_voltage_to_servo(voltage):
    """Scale voltage to servo position."""
    if voltage is None:
        return None
    # Assuming voltage is in the range 0-6V, scale to servo range (0-90 degrees)
    return int((voltage / 6.0) * 90)


def on_message(client, userdata, message):
    """Callback function to handle incoming MQTT messages."""
    try:
        data = json.loads(message.payload.decode("utf-8"))
        print(f"Received message on topic {message.topic}: {data}")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON from message: {e}")
        return

    for key, channel in servos.items():
        if key in data:
            voltage = data[key]
            servo_position = scale_voltage_to_servo(voltage)
            if servo_position is not None:
                print(f"Setting servo {channel} to position {servo_position} for {key}")
                pca.servo[channel].angle = servo_position
            else:
                print(f"No valid voltage for {key}, skipping servo {channel}")
        else:
            print(f"{key} not found in message data, skipping servo {channel}")


@click.command()
@click.option("--mqtt_host", default="localhost", help="MQTT broker host")
@click.option("--mqtt_port", default=1883, help="MQTT broker port")
@click.option(
    "--mqtt_topic", default="cubesatsim/data", help="MQTT topic to publish to"
)
@click.option("--mqtt_username", default=None, help="MQTT username (if required)")
@click.option("--mqtt_password", default=None, help="MQTT password (if required)")
def main(mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password):
    """Connect to the MQTT broker and print connection status."""
    client = mqtt.Client()
    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)

    try:
        client.connect(mqtt_host, mqtt_port, 60)
        print(f"Connected to MQTT broker at {mqtt_host}:{mqtt_port}")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return

    client.loop_start()

    client.subscribe(mqtt_topic)
    print(f"Subscribed to topic: {mqtt_topic}")
    client.on_message = on_message

    try:
        while True:
            pass  # Keep the script running
    except KeyboardInterrupt:
        print("Disconnecting from MQTT broker...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main(auto_envvar_prefix="CUBESATSIM")
    import sys

    sys.exit(0)
