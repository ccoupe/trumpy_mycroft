# 
# Mqtt <-> mycroft message bus. Very incomplete. 
# Very specific to my needs: Assumes homie and my hardware in it
# which is also very specific and only *looks* homie compatible.
# In particular, we turn on the 'voice' part of mycroft when we need it
# and off when we don't. It's not a general purpose mycroft!
#
# It's a horrible mix of paho-mqtt, websocket-client, and tornado.websocket
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
from lib.Constants import State, Event
import logging
import logging.handlers
import websocket

# Globals
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
  
# Send to Mycroft message bus
# TODO: check return codes
def mycroft_send(msg):
  ws = websocket.create_connection(settings.mycroft_uri)
  ws.send(msg)
  ws.close()

def mqtt_message(client, userdata, message):
  global settings, applog
  topic = message.topic
  payload = str(message.payload.decode("utf-8"))
  applog.info("mqtt: {} => {}".format(topic,payload))
  if topic == settings.hsub_say:
    mycroft_speak(payload)
  elif topic == settings.hsub_ask:
    mycroft_skill(payload)
  elif topic == settings.hsub_ctl:
    if payload == 'on':
      applog.info("Mycroft voice enabled")
      os.system('~/mycroft-core/start-mycroft.sh voice')
      time.sleep(1)
    elif payload == 'off':
      applog.info("Stopping Mycroft voice")
      os.system('~/mycroft-core/stop-mycroft.sh voice')
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
  mycroft_send(payload)  
  # enough time to get in the playing queue otherwise they go LIFO
  time.sleep(1) 
  return

# skills are triggered by utterences
def mycroft_skill(msg):
  global settings, applog
  applog.info("starting skill for: %s" % msg)
  mycroft_type = 'recognizer_loop:utterance'
  mycroft_data = '{"utterances": ["%s"]}' % msg
  message = '{"type": "' + mycroft_type + '", "data": ' + mycroft_data + '}'
  mycroft_send(message)
  return
  
# unused:
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

