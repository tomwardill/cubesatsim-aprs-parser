#!/bin/bash

# tee -p: keep telemetry flowing even if the SSTV detector stops reading
rtl_fm -f 434.9M -s 22050 - \
    | tee -p >(.venv/bin/python sstv_detect.py --mqtt_host mosquitto) \
    | multimon-ng -t raw -A -a AFSK1200 - \
    | .venv/bin/python main.py --mqtt_host mosquitto
