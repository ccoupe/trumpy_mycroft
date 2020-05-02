# 
# Mqtt <-> mycroft message bus. Very incomplete. 
# Very specific to my needs: Assumes homie and my hardware in it
# which is also very specific and only *looks* compatible.
# In particular, we turn the 'voice' part of mycroft on when we need it
# and off when we don't. It's not a general purpose mycroft
#
import paho.mqtt.client as mqtt
import sys
import json
import argparse
import warnings
from datetime import datetime
import time, threading, sched
import socket
import os
from lib.Settings import Settings
import logging
import logging.handlers
import websocket


settings = None
hmqtt = None
applog = None
isPi = False

def mqtt_conn_init(st):
  global hmqtt
  hmqtt = mqtt.Client(st.mqtt_client_name, False)
  hmqtt.connect(st.mqtt_server_ip, st.mqtt_port)
  prefix = 'homie/'+st.homie_device+'/speech'
  st.hsub_say = prefix+'/say/set'
  st.hsub_ask = prefix+'/ask/set'
  st.hsub_ctl = prefix+'/ctl/set'
  hmqtt.subscribe(st.hsub_say)
  hmqtt.subscribe(st.hsub_ask)
  hmqtt.subscribe(st.hsub_ctl)
  hmqtt.on_message = mqtt_message
  hmqtt.loop_start()

def mqtt_message(client, userdata, message):
  global settings, applog
  topic = message.topic
  payload = str(message.payload.decode("utf-8"))
  applog.info("mqtt: {} => {}".format(topic,payload))
  if topic == settings.hsub_say:
    mycroft_speak(payload)
  elif topic == settings.hsub_ask:
    mycroft_query(payload)
  elif topic == settings.hsub_ctl:
    if payload == 'on':
      applog.info("Mycroft voice enabled")
      os.system('~/mycroft-core/start-mycroft.sh voice')
      time.sleep(1)
      settings.myc_ws = websocket.create_connection(settings.mycroft_uri)
    elif payload == 'off':
      applog.info("Stopping Mycroft voice")
      os.system('~/mycroft-core/stop-mycroft.sh voice')
      settings.myc_ws.close()
  else:
    applog.debug("unknown topic {}".format(topic))
    
def mycroft_speak(message):
  global settings, applog
  mycroft_type = 'recognizer_loop:utterance'
  payload = json.dumps({
    "type": mycroft_type,
    "context": "",
    "data": {
        "utterances": ["say {}".format(message)]
    }
  })
  applog.info("speaking %s" % payload)
  result = settings.myc_ws.send(payload)  
  applog.debug("rtn: %s" % result)
  print("Spk:", self.myc_conn.recv())
  print("Spk:", self.myc_conn.recv())
  # enough time to get in the playing queue otherwise they go LIFO
  time.sleep(1) 
  return
  
def mycroft_query(msg):
  global settings, applog
  applog.info("starting query for: %s" % msg)
  mycroft_type = 'question:query'
  mycroft_data = '{"phrase": "%s"}' % msg
  message = '{"type": "' + mycroft_type + '", "data": ' + mycroft_data + '}'
  settings.myc_ws.send(message)
  print("qry:", self.myc_conn.recv())
  print("qry:", self.myc_conn.recv())
  time.sleep(1)
  print("qry:", self.myc_conn.recv())
  print("qry:", self.myc_conn.recv())
  
def rest_server_init(st):
  pass

def main():
  global isPi, settings, hmqtt, applog
  # process cmdline arguments
  loglevels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
  ap = argparse.ArgumentParser()
  ap.add_argument("-c", "--conf", required=True, type=str,
    help="path and name of the json configuration file")
  ap.add_argument("-s", "--syslog", action = 'store_true',
    default=False, help="use syslog")
  args = vars(ap.parse_args())
  
  # logging setup
  applog = logging.getLogger('mqttmycroft')
  if args['syslog']:
    applog.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    # formatter for syslog (no date/time or appname.
    formatter = logging.Formatter('%(name)s-%(levelname)-5s: %(message)s')
    handler.setFormatter(formatter)
    applog.addHandler(handler)
  else:
    logging.basicConfig(level=logging.DEBUG,datefmt="%H:%M:%S",format='%(asctime)s %(levelname)-5s %(message)s')
  
  isPi = os.uname()[4].startswith("arm")
  
  settings = Settings(args["conf"], 
                      applog)
  settings.print()
  mqtt_conn_init(settings)
  rest_server_init(settings)
  
  # do something magic to integrate the event loops
  while True:
    time.sleep(5)

if __name__ == '__main__':
  sys.exit(main())

