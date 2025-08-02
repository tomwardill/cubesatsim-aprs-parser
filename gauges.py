from datetime import datetime
import json
from time import sleep

from adafruit_servokit import ServoKit
from ht16k33 import HT16K33SegmentGen
import busio
import board
import digitalio
import adafruit_character_lcd.character_lcd_spi as character_lcd
import paho.mqtt.client as mqtt
import click

number_channels = 16
servos = {
    "battery_current": 0,
    "BAT_voltage": 4,
    "MINUS_X_voltage": 1,
    "PLUS_X_voltage": 5,
    "MINUS_Y_voltage": 2,
    "PLUS_Y_voltage": 6,
    "MINUS_Z_voltage": 3,
    "PLUS_Z_voltage": 7,
}

pca = ServoKit(channels=number_channels)

i2c = busio.I2C(scl=board.SCL, sda=board.SDA)
frame_display = HT16K33SegmentGen(i2c, i2c_address=0x70, digits=8)
rx_freq_display = HT16K33SegmentGen(i2c, i2c_address=0x71, digits=8)
tx_freq_display = HT16K33SegmentGen(i2c, i2c_address=0x72, digits=8)

spi = busio.SPI(board.SCK, MOSI=board.MOSI)
latch = digitalio.DigitalInOut(board.D8)
cols = 20
rows = 4
lcd = character_lcd.Character_LCD_SPI(spi, latch, cols, rows)

frame_count = 0


def segment_display(led: HT16K33SegmentGen, message: str):

    if len(message) < 8:
        message = message.zfill(8)

    led.clear()
    for i, char in enumerate(message):
        if i < 8:
            led.set_character(char, i)
    led.draw()


def matrix_display(lcd: character_lcd.Character_LCD_SPI, payload: dict):
    """Display a message on the LCD."""
    lcd.clear()

    message = ""
    message += payload.get("callsign", "Unknown") + "\n"
    message += f"{payload.get('battery_voltage', '0.0V')}V {payload.get('battery_current', '0.0mA')}mA\n"
    message += f"{payload.get('mpu_roll', '0.0')}, {payload.get('mpu_pitch', '0.0')}, {payload.get('mpu_yaw', '0.0')}\n"
    message += f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    lcd.message = message
    print(f"LCD Display: {message}")


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
        global frame_count
        frame_count = frame_count + 1
        segment_display(frame_display, str(frame_count).zfill(8))
        matrix_display(lcd, data)
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON from message: {e}")
        return

    for key, channel in servos.items():
        if key in data:
            voltage = data[key]
            if key != "battery_current":
                servo_position = scale_voltage_to_servo(voltage)
            else:
                # For battery current, scale to a different range if needed
                # Here we assume battery current is in mA and scale it to 0-90 degrees
                # For battery current, center at 45 degrees and scale +/-45 degrees
                # Assuming a typical range of 0-1000 mA
                servo_position = 45 + int(((voltage / 1000.0) * 90) - 45)
                # Ensure we stay within valid servo range (0-90)
                servo_position = max(0, min(90, servo_position))
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

    # Sweep all servos because it looks cool
    for channel in range(number_channels):
        pca.servo[channel].angle = 0
        print(f"Sweeping servo {channel} to position 0")
    sleep(1)
    for channel in range(number_channels):
        pca.servo[channel].angle = 90
        print(f"Sweeping servo {channel} to position 90")
    sleep(1)

    # Zero all servos at startup
    for channel in range(number_channels):
        if channel == 0:
            pca.servo[channel].angle = 45  # Center battery current servo
        else:
            pca.servo[channel].angle = 0
        print(f"Initialized servo {channel} to position 0")

    # Initialize displays
    display(frame_display, "0")
    display(rx_freq_display, "434900")
    display(tx_freq_display, "435000")


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
