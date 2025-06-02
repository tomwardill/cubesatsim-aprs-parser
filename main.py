import sys
import re
from typing import Generator, Tuple

import click
from latloncalc.latlon import LatLon, string2latlon
import paho.mqtt.client as mqtt


def capture_stdin() -> Generator[str]:
    try:
        print("Listening for APRS data on stdin. Press Ctrl+C to exit.")
        for line in iter(sys.stdin.readline, ""):
            line = line.strip()
            if line.startswith("APRS:"):
                yield line
            else:
                sys.stderr.write(f"Skipping line: {line}\n")
                sys.stderr.flush()
    except KeyboardInterrupt:
        sys.stdout.flush()
        pass


def decode_position(encoded_position: str) -> LatLon:
    positions = re.findall(
        r"[0-9]{4}\.[0-9]{2}[A-Z]",
        encoded_position.encode("unicode_escape").replace(b"\\x", b"").decode(),
    )

    spaced_latitude = (
        f"{positions[0][:2]} {positions[0][2:4]} {positions[0][5:7]} {positions[0][7:]}"
    )
    spaced_longitude = (
        f"{positions[1][:2]} {positions[1][2:4]} {positions[1][5:7]} {positions[1][7:]}"
    )
    return string2latlon(spaced_latitude, spaced_longitude, "d% %m% %S% %H")


def decode_battery(encoded_battery: str) -> dict:
    search = re.search("BAT ([\\d]+\\.[\\d]+) ([+-]?\\d+\\.\\d+) ", encoded_battery)
    return {
        "battery_voltage": float(search.group(1)) if search else None,
        "battery_current": float(search.group(2)) if search else None,
    }


def decode_bme_sensor(encoded_bme: str) -> dict:
    search = re.search(
        "BME280 ([\\d]+\\.[\\d]+) ([\\d]+\\.[\\d]+) ([\\d]+\\.[\\d]+) ([\\d]+\\.[\\d]+)",
        encoded_bme,
    )
    return {
        "bme_temperature": float(search.group(1)) if search else None,
        "bme_pressure": float(search.group(2)) if search else None,
        "bme_altitude": float(search.group(3)) if search else None,
        "bme_humidity": float(search.group(4)) if search else None,
    }


def decode_mpu6050(encoded_mpu: str) -> dict:
    search = re.search(
        "MPU6050 ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+)",
        encoded_mpu,
    )
    return {
        "mpu_accel_x": float(search.group(1)) if search else None,
        "mpu_accel_y": float(search.group(2)) if search else None,
        "mpu_accel_z": float(search.group(3)) if search else None,
        "mpu_gyro_x": float(search.group(4)) if search else None,
        "mpu_gyro_y": float(search.group(5)) if search else None,
        "mpu_gyro_z": float(search.group(6)) if search else None,
    }


def decode_gps(encoded_gps: str) -> dict:
    search = re.search(
        "GPS ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+) ([+-]?[\\d]+\\.[\\d]+)",
        encoded_gps,
    )
    return {
        "gps_latitude": float(search.group(1)) if search else None,
        "gps_longitude": float(search.group(2)) if search else None,
        "gps_altitude": float(search.group(3)) if search else None,
    }


def decode_mcu_temp(encoded_mcu: str) -> dict:
    search = re.search("TMP ([\\d]+\\.[\\d]+)", encoded_mcu)
    return {
        "mcu_temperature": float(search.group(1)) if search else None,
    }


def decode_aprs(aprs: str) -> dict:
    """Decode the APRS data."""
    data = {}
    try:
        # Remove the 'APRS:' prefix
        aprs = aprs[5:].strip()

        # Split the APRS data into parts
        parts = aprs.split(" ")

        # Extract the callsign and position
        callsign, position = parts[0].split(">")[0], parts[0].split(">")[1]
        data["callsign"] = callsign
        latlng = decode_position(position)
        data["latitude"] = latlng.lat.to_string("D")
        data["longitude"] = latlng.lon.to_string("D")

        data.update(decode_battery(aprs))
        data.update(decode_bme_sensor(aprs))
        data.update(decode_mpu6050(aprs))
        data.update(decode_gps(aprs))
        data.update(decode_mcu_temp(aprs))

        # Add raw APRS data
        data["raw_aprs"] = aprs

    except Exception as e:
        sys.stderr.write(f"Error decoding APRS data: {e}\n")
        sys.stderr.flush()
    return data


def connect_to_mqtt(
    mqtt_host: str,
    mqtt_port: int,
    mqtt_username: str,
    mqtt_password: str,
):

    client = mqtt.Client()
    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)

    client.connect(mqtt_host, mqtt_port, 60)
    return client


@click.command()
@click.option("--mqtt_host", default="localhost", help="MQTT broker host")
@click.option("--mqtt_port", default=1883, help="MQTT broker port")
@click.option(
    "--mqtt_topic", default="cubesatsim/data", help="MQTT topic to publish to"
)
@click.option("--mqtt_username", default=None, help="MQTT username (if required)")
@click.option("--mqtt_password", default=None, help="MQTT password (if required)")
def main(mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password):
    """Capture stdin and print each line."""
    client = connect_to_mqtt(
        mqtt_host, mqtt_port, mqtt_username, mqtt_password
    )
    for aprs in capture_stdin():
        data = decode_aprs(aprs)
        if data:
            client.publish(mqtt_topic, str(data))
            print(f"Published to {mqtt_topic}: {data}")
        else:
            print("No valid APRS data to publish.")


if __name__ == "__main__":
    main(auto_envvar_prefix="CUBESATSIM")
    sys.exit(0)
