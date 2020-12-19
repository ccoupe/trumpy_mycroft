# 
# Mqtt <-> mycroft message bus. Very incomplete. 
# Very specific to my needs: Assumes homie and my hardware in it
# which is also very specific and only *looks* homie compatible.
# In particular, we turn on the 'voice' part of mycroft when we need it
# and off when we don't. It's not a general purpose mycroft!
#
# It's a horrible mix of paho-mqtt, websockets and websocket-client
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
#from lib.Constants import State, Event
import logging
import logging.handlers
import asyncio
import websockets
import websocket
	

# Globals
settings = None
hmqtt = None
applog = None
isPi = False
muted = False
five_min_thread = None

def mqtt_conn_init(st):
  global hmqtt
  hmqtt = mqtt.Client(st.mqtt_client_name, False)
  hmqtt.connect(st.mqtt_server_ip, st.mqtt_port)
  prefix = 'homie/'+st.homie_device+'/speech'
  st.hsub_say = prefix+'/say/set'
  st.hsub_ask = prefix+'/ask/set'
  st.hsub_ctl = prefix+'/ctl/set'
  st.hpub_reply = prefix+'/reply/set'
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
  global settings, applog, muted
  topic = message.topic
  payload = str(message.payload.decode("utf-8"))
  applog.info("mqtt: {} => {}".format(topic,payload))
  if topic == settings.hsub_say:
    mycroft_speak(payload)
  elif topic == settings.hsub_ask:
    mycroft_skill(payload)
  elif topic == settings.hsub_ctl:
    isPi = os.uname()[4].startswith("arm")
    if isPi:
      home = '/home/pi'
    else:
      home = 'home/ccoupe'
    if payload == 'on' and muted == True:
      applog.info("Mycroft voice enabled")
      #os.system(f'{home}/mycroft-core/start-mycroft.sh voice')
      #os.system(f'pacmd set-source-mute 1 0')
      mycroft_type = 'mycroft.mic.unmute'
      msg = json.dumps({
        "type": mycroft_type,
        "context": "",
        "data": {} 
      })
      mycroft_send(msg)
      # mycroft needs to be told it can listen after unmute. When it works.
      '''
      time.sleep(0.1)
      mycroft_type = 'recognizer_loop:wake_up'
      #mycroft_type = 'mycroft.mic.listen'
      msg = json.dumps({
        "type": mycroft_type,
        "context": "",
        "data": {} 
      })
      mycroft_send(msg)
      '''
      muted = False
      #time.sleep(1)
    elif payload == 'off' and muted == False:
      applog.info("Stopping Mycroft voice")
      #os.system(f'{home}/mycroft-core/stop-mycroft.sh voice')
      #os.system(f'pacmd set-source-mute 1 1')
      mycroft_type = 'mycroft.mic.mute'
      msg = json.dumps({
        "type": mycroft_type,
        "context": "",
        "data": {} 
      })
      mycroft_send(msg)
      muted = True
    elif payload == '?':
      mycroft_mute_status()
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
  
def mycroft_mute_status():
  global settings, applog, muted
  mycroft_type = 'mycroft.mic.get_status'
  msg = json.dumps({
    "type": mycroft_type,
    "context": "",
    "data": {} 
  })
  ws = websocket.create_connection(settings.mycroft_uri)
  ws.send(msg)
  #applog.info(f'qry1: {ws.recv()}') # {"type": "connected", "data": {}, "context": {}}
  ws.recv()
  #applog.info(f'qry2: {ws.recv()}') # {"type": "mycroft.mic.get_status", "context": "", "data": {}}
  ws.recv()
  #applog.info(f'qry3: {ws.recv()}') # {"type": "mycroft.mic.get_status.response", "data": {"muted": false}, "context": {}}
  js = ws.recv()
  dt = json.loads(js)
  muted = dt['data']['muted']
  applog.info(f'background check muted: {muted}')
  ws.close()
  
def long_timer_fired():
  global five_min_thread
  mycroft_mute_status()
  five_min_thread = threading.Timer(5 * 60, long_timer_fired)
  five_min_thread.start()

def five_min_timer():
  global five_min_thread
  print('creating long timer')
  five_min_thread = threading.Timer(1.5 * 60, long_timer_fired)
  five_min_thread.start()

    
# ----- websocket server - send payload to mqtt ../reply/set
  
async def wss_reply(ws, path):
  global hmqtt, settings, applog
  message = await ws.recv()
  applog.info('wss: message received:  %s' % message)
  hmqtt.publish(settings.hpub_reply, message)

def wss_server_init(st):
  global wss_server
  #websocket.enableTrace(True)
  IPAddr = socket.gethostbyname(socket.gethostname()) 
  wsadr = "ws://%s:5125/reply" % IPAddr
  applog.info(wsadr)
  wss_server = websockets.serve(wss_reply, IPAddr, 5125)

    
def main():
  global isPi, settings, hmqtt, applog, wss_server
  # process cmdline arguments
  loglevels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
  ap = argparse.ArgumentParser()
  ap.add_argument("-c", "--conf", required=True, type=str,
    help="path and name of the json configuration file")
  ap.add_argument("-s", "--syslog", action = 'store_true',
    default=False, help="use syslog")
  args = vars(ap.parse_args())
  
  # logging setup
  # Note websockets is very chatty at DEBUG level. Sigh.
  applog = logging.getLogger('mqttmycroft')
  if args['syslog']:
    applog.setLevel(logging.INFO)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    # formatter for syslog (no date/time or appname.
    formatter = logging.Formatter('%(name)s-%(levelname)-5s: %(message)s')
    handler.setFormatter(formatter)
    applog.addHandler(handler)
  else:
    logging.basicConfig(level=logging.INFO,datefmt="%H:%M:%S",format='%(asctime)s %(levelname)-5s %(message)s')
  
  isPi = os.uname()[4].startswith("arm")
  
  settings = Settings(args["conf"], 
                      applog)
  settings.print()
  mqtt_conn_init(settings)
  wss_server_init(settings)
  five_min_timer()
  asyncio.get_event_loop().run_until_complete(wss_server)
  asyncio.get_event_loop().run_forever()

  # do something magic to integrate the event loops? 
  while True:
    time.sleep(5)

if __name__ == '__main__':
  sys.exit(main())

