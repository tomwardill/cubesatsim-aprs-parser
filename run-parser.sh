#!/bin/bash

# tee -p: keep telemetry flowing even if one of the SSTV readers stops
rtl_fm -f 434.9M -s 22050 - \
    | tee -p >(.venv/bin/python sstv_detect.py --mqtt_host mosquitto) \
             >(.venv/bin/python sstv_decode.py --mqtt_host mosquitto) \
    | multimon-ng -t raw -A -a AFSK1200 - \
    | .venv/bin/python main.py --mqtt_host mosquitto
