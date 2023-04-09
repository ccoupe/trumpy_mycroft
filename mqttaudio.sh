#!/usr/bin/env bash
#sudo killall bluealsa
cd /usr/local/lib/mqttaudio
python3 bridge.py -s -c pi4.json
