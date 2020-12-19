#!/usr/bin/env bash
#sudo killall bluealsa
#echo -e "connect 4C:8F:C6:6A:98:1E" | bluetoothctl
echo -e "connect DE:B0:D2:C5:0B:7C" | bluetoothctl
cd /usr/local/lib/mqttmycroft
python3 bridge.py -s -c trumpy.json
