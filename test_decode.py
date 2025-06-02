from main import (
    decode_aprs,
    decode_position,
    decode_battery,
    decode_bme_sensor,
    decode_mpu6050,
    decode_gps,
    decode_mcu_temp
)

sample = "APRS: 2E0JJI-11>APCSS:=5324.08N\00132.20WShi hi BAT 4.42 -340.3 OK BME280 42.45 993.45 166.17 14.49 MPU6050 8.60 -2.72 0.15 0.04 -0.01 1.02 GPS 0.0000 0.0000 0.00 TMP 43.50"


def test_with_sample():
    result = decode_aprs(sample)
    assert result["callsign"] == "2E0JJI-11"
    assert result["latitude"] == "53.40222222222222"
    assert result["longitude"] == "-1.5388888888888888"
    assert result["battery_voltage"] == 4.42
    assert result["battery_current"] == -340.3
    assert result["bme_temperature"] == 42.45
    assert result["bme_pressure"] == 993.45
    assert result["bme_altitude"] == 166.17
    assert result["bme_humidity"] == 14.49
    assert result["mpu_accel_x"] == 8.60
    assert result["mpu_accel_y"] == -2.72
    assert result["mpu_accel_z"] == 0.15
    assert result["mpu_gyro_x"] == 0.04
    assert result["mpu_gyro_y"] == -0.01
    assert result["mpu_gyro_z"] == 1.02
    assert result["gps_latitude"] == 0.0
    assert result["gps_longitude"] == 0.0
    assert result["gps_altitude"] == 0.0
    assert result["mcu_temperature"] == 43.50
    assert result["raw_aprs"] == sample.split("APRS: ")[1]


def test_decode_position():
    result = decode_position("5324.08N\00132.20W")
    assert result.lat.to_string("D") == "53.40222222222222"
    assert result.lon.to_string("D") == "-1.5388888888888888"


def test_decode_battery():
    battery_details = decode_battery(sample)
    assert battery_details["battery_voltage"] == 4.42
    assert battery_details["battery_current"] == -340.3


def test_decode_bme_sensor():
    result = decode_bme_sensor(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["bme_temperature"] == 42.45
    assert result["bme_pressure"] == 993.45
    assert result["bme_altitude"] == 166.17
    assert result["bme_humidity"] == 14.49


def test_decode_mpu6050():
    result = decode_mpu6050(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["mpu_accel_x"] == 8.60
    assert result["mpu_accel_y"] == -2.72
    assert result["mpu_accel_z"] == 0.15
    assert result["mpu_gyro_x"] == 0.04
    assert result["mpu_gyro_y"] == -0.01
    assert result["mpu_gyro_z"] == 1.02


def test_decode_gps():
    result = decode_gps(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["gps_latitude"] == 0.0  # GPS values in sample are 0.0000
    assert result["gps_longitude"] == 0.0
    assert result["gps_altitude"] == 0.0

def test_decode_mcu_temp():
    result = decode_mcu_temp(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["mcu_temperature"] == 43.50
