#!/bin/bash

rtl_fm -f 434.9M -s 22050 - | multimon-ng -t raw -A -a AFSK1200 - | .venv/bin/python main.py
