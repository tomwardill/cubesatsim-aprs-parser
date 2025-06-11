from main import (
    decode_aprs,
    decode_position,
    decode_battery,
    decode_bme_sensor,
    decode_mpu6050,
    decode_voltages
)

sample = "APRS: 2E0JJI-11>APCSS:=5324.08N\00132.20WShi hi BAT 4.32 -514.7 VOL 4.25 1.71 3.33 1.49 2.64 0.86 4.49 0.00 OK BME280 27.55 998.38 124.55 27.48 MPU6050 -2.06 0.16 0.00"


def test_with_sample():
    result = decode_aprs(sample)
    assert result["callsign"] == "2E0JJI-11"
    assert result["latitude"] == "53.40222222222222"
    assert result["longitude"] == "-1.5388888888888888"
    assert result["battery_voltage"] == 4.32
    assert result["battery_current"] == -514.7
    assert result["bme_temperature"] == 27.55
    assert result["bme_pressure"] == 998.38
    assert result["bme_altitude"] == 124.55
    assert result["bme_humidity"] == 27.48
    assert result["mpu_yaw"] == -2.06
    assert result["mpu_pitch"] == 0.16
    assert result["mpu_roll"] == 0.00
    assert result["PLUS_X_voltage"] == 4.25
    assert result["MINUS_X_voltage"] == 1.71
    assert result["PLUS_Y_voltage"] == 3.33
    assert result["MINUS_Y_voltage"] == 1.49
    assert result["PLUS_Z_voltage"] == 2.64
    assert result["MINUS_Z_voltage"] == 0.86
    assert result["BAT_voltage"] == 4.49
    assert result["BUS_voltage"] == 0.00
    assert result["raw_aprs"] == sample.split("APRS: ")[1]


def test_decode_position():
    result = decode_position("5324.08N\00132.20W")
    assert result.lat.to_string("D") == "53.40222222222222"
    assert result.lon.to_string("D") == "-1.5388888888888888"


def test_decode_battery():
    battery_details = decode_battery(sample)
    assert battery_details["battery_voltage"] == 4.32
    assert battery_details["battery_current"] == -514.7


def test_decode_bme_sensor():
    result = decode_bme_sensor(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["bme_temperature"] == 27.55
    assert result["bme_pressure"] == 998.38
    assert result["bme_altitude"] == 124.55
    assert result["bme_humidity"] == 27.48


def test_decode_mpu6050():
    result = decode_mpu6050(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["mpu_yaw"] == -2.06
    assert result["mpu_pitch"] == 0.16
    assert result["mpu_roll"] == 0.00


def test_decode_voltages():
    result = decode_voltages(sample)
    assert isinstance(
        result, dict
    )  # Assuming it returns an empty dict or similar structure
    assert result["PLUS_X_voltage"] == 4.25
    assert result["MINUS_X_voltage"] == 1.71
    assert result["PLUS_Y_voltage"] == 3.33
    assert result["MINUS_Y_voltage"] == 1.49
    assert result["PLUS_Z_voltage"] == 2.64
    assert result["MINUS_Z_voltage"] == 0.86
    assert result["BAT_voltage"] == 4.49
    assert result["BUS_voltage"] == 0.00
