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
from threading import Lock, Thread
import socket
import os
from lib.Settings import Settings
from lib.Audio import AudioDev
from subprocess import Popen
import urllib.request
#from lib.Constants import State, Event
import logging
import logging.handlers
import asyncio
import websockets
import websocket
import pulsectl
# for calling GLaDOS TTS
from subprocess import call
import urllib.parse
import re
import speech_recognition as speech_recog


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
  toplevel = 'homie/'+st.homie_device
  hmqtt.publish(toplevel, None, qos=1,retain=True)
  prefix = toplevel + '/speech'
  hmqtt.publish(prefix+'/say/set', None, qos=1,retain=False)
  st.hsub_say = prefix+'/say/set'
  hmqtt.subscribe(st.hsub_say)
  
  hmqtt.publish(prefix+'/ask/set', None, qos=1,retain=False)
  st.hsub_ask = prefix+'/ask/set'
  hmqtt.subscribe(st.hsub_ask)
  
  hmqtt.publish(prefix+'/ctl/set', None, qos=1,retain=False)
  st.hsub_ctl = prefix+'/ctl/set'
  hmqtt.subscribe(st.hsub_ctl)
  
  # publish to reply - do not subscribe to it.
  hmqtt.publish(prefix+'/reply/set', None, qos=1,retain=False)
  st.hpub_reply = prefix+'/reply/set'
  #hmqtt.subscribe(st.hsub_reply)
  
  
  st.hsub_play = 'homie/'+st.homie_device+'/player/url/set'
  hmqtt.publish(st.hsub_play, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_play)
  
  st.hsub_play_vol = 'homie/'+st.homie_device+'/player/volume/set'
  hmqtt.publish(st.hsub_play_vol, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_play_vol)

  st.hsub_chime = 'homie/'+st.homie_device+'/chime/state/set'
  hmqtt.publish(st.hsub_chime, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_chime)
  
  st.hsub_chime_vol = 'homie/'+st.homie_device+'/chime/volume/set'
  hmqtt.publish(st.hsub_chime_vol, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_chime_vol)
  
  st.hsub_siren = 'homie/'+st.homie_device+'/siren/state/set'
  hmqtt.publish(st.hsub_siren, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_siren)
  
  st.hsub_siren_vol = 'homie/'+st.homie_device+'/siren/volume/set'
  hmqtt.publish(st.hsub_siren_vol, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_siren_vol)
  
  st.hsub_strobe = 'homie/'+st.homie_device+'/strobe/state/set'
  hmqtt.publish(st.hsub_strobe, None, qos=1,retain=False)
  hmqtt.subscribe(st.hsub_strobe)
      
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
  applog.info(f"mqtt: {topic} => {payload}")
  if payload is None:
    return
  # guard again payloads of None (happens at setup time, BTW)
  # convert to string and check if the lenth is more than zero
  if topic == settings.hsub_say and len(str(payload)) > 0:
    if settings.engine_nm == 'mycroft':
      mycroft_speak(payload)
    else:
      glados_speak(payload)
  elif topic == settings.hsub_ask and len(str(payload)) > 0:
    if settings.engine_nm == 'mycroft':
      mycroft_skill(payload)
    else:
      glados_ask(payload)
  elif topic == settings.hsub_ctl and len(str(payload)) > 0:
    if payload == 'on' and muted == True:
      '''
      applog.info("Mycroft voice enabled")
      mycroft_type = 'mycroft.mic.unmute'
      msg = json.dumps({
        "type": mycroft_type,
        "context": "",
        "data": {} 
      })
      mycroft_send(msg)
      '''
      # Use pulseaudio to unmute mic and speaker
      applog.info('Pulseaudo unmuted')
      settings.pulse.source_mute(settings.microphone_index, 0)
      settings.pulse.sink_mute(settings.speaker_index, 0)
      '''
      # mycroft needs to be told it can listen after unmute. When it works.
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
      '''
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
      '''
      # Use pulseaudio to mute mic and speaker
      applog.info('Pulseaudo muted')
      settings.pulse.source_mute(settings.microphone_index, 1)
      settings.pulse.sink_mute(settings.speaker_index, 1)
      muted = True
    elif payload == '?':
      if settings.engine_nm == 'mycroft':
        mycroft_mute_status()
        
  elif topic == settings.hsub_play and len(str(payload)) > 0:
    player_thr = Thread(target=playUrl, args=(payload,))
    player_thr.start()
  elif topic == settings.hsub_chime and len(str(payload)) > 0:
    applog.warn(f'chime payload is {type(payload)}: {payload}')
    chime_thr = Thread(target=chimeCb, args=(payload,))
    chime_thr.start()
  elif topic == settings.hsub_siren and len(str(payload)) > 0:
    siren_thr = Thread(target=sirenCb, args=(payload,))
    siren_thr.start()
  elif topic == settings.hsub_strobe and len(str(payload)) > 0:
    strobe_thr = Thread(target=strobeCb, args=(payload,))
    strobe_thr.start()
  elif topic == settings.hsub_play_vol and len(str(payload)) > 0:
    vol = int(payload)
    settings.player_vol = vol
  elif topic == settings.hsub_chime_vol and len(str(payload)) > 0:
    vol = int(payload)
    settings.chime_vol = vol
  elif topic == settings.hsub_siren_vol and len(str(payload)) > 0:
    vol = int(payload)
    settings.siren_vol = vol

  else:
    applog.debug("unknown topic {}".format(topic))
    

# Could use websockets instead of mqtt if we wanted a synchronous send/recv
def mic_icon(onoff):
  global hmqtt, applog, settings
  if settings.mic_pub_type == 'login':
    dt = {}
    if onoff:
      dt['cmd'] = 'mic_on'
    else:
      dt['cmd'] = 'mic_off'
    hmqtt.publish(settings.mic_pub_topic, json.loads(dt), qos=1)
  else:
    if onoff:
      cmd = "Speak now"
    else:
      cmd = "Don't talk"
    hmqtt.publish(settings.mic_pub_topic, cmd, qos=1)
  # expidite the message. Doc says don't do this. They mean it.
  # hmqtt.loop()
    
  
def mycroft_speak(message):
  global settings, applog,  muted
  if muted:
    # unmute
    settings.pulse.source_mute(settings.microphone_index, 0)
    settings.pulse.sink_mute(settings.speaker_index, 0)
  # TODO: set volume first?
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
  
def glados_speak(message):
  global settings, applog,  muted
  if muted:
    # unmute
    settings.pulse.source_mute(settings.microphone_index, 0)
    settings.pulse.sink_mute(settings.speaker_index, 0)
  # TODO: set volume first?
  fetchTTSSample(message)
  time.sleep(1) 
  return
  
# Glados stuff Borrowed from nerdaxic: 
# Note 'aplay' is synchronous - we wail in playFile until
# the sound is finished playing. It is highly likely we
# depend on that behavior instead of using state machines, callbacks
# and other joyful things.
def playFile(filename):
  global audiodev
  call(["aplay", "-q", filename])	
  

# Turns units etc into speakable text
def cleanTTSLine(line):
  line = line.replace("sauna", "incinerator")
  line = line.replace("'", "")
  line = line.lower()
  
  if re.search("-\d", line):
    line = line.replace("-", "negative ")
  
  return line

# Get GLaDOS TTS Sample
def fetchTTSSample(line):
  global settings, applog, hmqtt
  text = urllib.parse.quote(cleanTTSLine(line))
  TTSCommand = 'curl -L --retry 5 --get --fail -o /tmp/GLaDOS-tts-temp-output.wav '+settings.tts_url+text
  
  TTSResponse = os.system(TTSCommand)
  
  if(TTSResponse != 0):
    applog.info(f'Failed: TTS fetch phrase {line}')
    return False
    
  playFile("/tmp/GLaDOS-tts-temp-output.wav")
  applog.info(f'Success: TTS played {line}')
  return True
  

def glados_answer():
  global applog, microphone,recognizer
  # get a .wav from the microphone
  # send that to STT (whisper)
  # return the response. 
  fi = '/tmp/whisper-in.wav'
  fo = '/tmp/whisper-out.json'
  import speech_recognition as sr
  r = sr.Recognizer()
  with sr.Microphone() as source:
    audio = r.listen(source)
    with open(fi, "wb") as f:
      f.write(audio.get_wav_data())
    applog.info("calling whisper")
    cmd = f'curl -F file=@{fi} -o {fo} bronco.local:5003'
    os.system(cmd)
    dt = {}
    with open(fo,"r") as f:
      dt = json.load(f)
      # print(dt)
    msg = dt['results'][0]['transcript']
    applog.info(f'Whisper returns: {msg}')
    # publish it to mqtt "homie/"+hdevice+"/speech/reply/set"
    hmqtt.publish(settings.hpub_reply, msg)
    mic_icon(False)


def glados_ask(code):
  global settings, applog
  # some messages from trumpybear are mycroft codes. Glados needs to
  # ask the appropriate question.
  if code == 'nameis':
    msg = "Hello sweety! Tell me your name?"
  elif code == 'music_talk':
    msg = 'I could play you a favorite tune of mine or we could \
have a conversation. Say music or talk.'
  else:
    msg = code
  # speak our prompt msg
  fetchTTSSample(msg)
  mic_icon(True)
  # because of threading and sync issues (mqtt plus ...)
  # start a new thread to give mic_icon a chance to run first.
  answer_thr = Thread(target=glados_answer, args=())
  answer_thr.start()
  

# for ask, mycroft skills are triggered by utterences that return
# a string. That skill is either clever or a hack - your choice.
# The hack is the skill sends the response to mqtt so the bridge 
# may never see it.
def mycroft_skill(code):
  global settings, applog
  if code == 'nameis':
    msg = 'awaken the hooligans'
  elif code == 'music_talk':
    msg = 'send in the terrapin'
  else:
    applog.info(f'Missing "code" to start a skill: {code}')
    return
  applog.info("starting skill for: %s" % msg)
  mycroft_type = 'recognizer_loop:utterance'
  mycroft_data = '{"utterances": ["%s"]}' % msg
  message = '{"type": "' + mycroft_type + '", "data": ' + mycroft_data + '}'
  mycroft_send(message)
  return
  
def mycroft_mute_status():
  global settings, applog, muted
  '''
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
  # dt == {'type': 'mycroft-reminder.mycroftai:reminder', 'data': {}, 'context': {}}
  # dt == {'type': 'mycroft-configuration.mycroftai:ConfigurationSkillupdate_remote', 'data': 'UpdateRemote', 'context': {}}
  if isinstance(dt, dict):
    data = dt['data']
    if isinstance(data, dict):
      if data.get('muted', None):
        muted = dt['data']['muted']
        applog.info(f'background check muted: {muted}')
      else:
        applog.info(f'response from mycroft.mic.get_status is empty: {dt}')
  else:
    applog.info(f'response from mycroft.mic.get_status malformed: {dt}')
  ws.close()
  '''
  
def long_timer_fired():
  global five_min_thread
  #mycroft_mute_status()
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

def pulse_setup(settings):
  pulse = pulsectl.Pulse('mqttmycroft')
  for src in pulse.source_list():
    if src.name == settings.microphone:
      settings.microphone_index = src.index
      settings.source = src
      pulse.default_set(src)
      applog.info(f'Microphone index = {settings.microphone_index}')
  for sink in pulse.sink_list():
    #applog.info(f'{sink.name} =? {settings.speaker}')
    if sink.name == settings.speaker:
      settings.speaker_index = sink.index
      settings.sink = sink
      pulse.default_set(sink)
      applog.info(f'Speaker index = {settings.speaker_index}')
        
  if settings.microphone_index is None:
    applog.error('Missing or bad Microphone setting')
    exit()
  else:
    pulse.volume_set_all_chans(settings.source, settings.microphone_volume)
    
  if settings.speaker_index is None:
    applog.error('Missing or bad Speaker setting')
    exit()
  else:
    pulse.volume_set_all_chans(settings.sink, settings.speaker_volume)
    
  # save the pulse object so we can call it later.
  settings.pulse = pulse


# Hubitat 'devices' 
def mp3_player(fp):
  global player_obj, applog, audiodev
  cmd = f'{audiodev.play_mp3_cmd} {fp}'
  player_obj = Popen('exec ' + cmd, shell=True)
  player_obj.wait()

# Restore volume if it was changed
def player_reset():
  global settings, applog, audiodev
  if settings.player_vol != settings.player_vol_default and not audiodev.broken:
    applog.info(f'reset player vol to {settings.player_vol_default}')
    settings.player_vol = settings.player_vol_default
    audiodev.set_volume(settings.player_vol_default)

def playUrl(url):
  global hmqtt, audiodev, applog, settings, player_mp3, player_obj
  applog.info(f'playUrl: {url}')
  tmpf = "/tmp/mqttaudio-tmp.f"
  if url == 'off':
    if player_mp3 != True:
      return
    player_mp3 = False
    applog.info("killing tts")
    player_obj.terminate()
    player_reset()
  else:
    try:
      urllib.request.urlretrieve(url, tmpf)
    except:
      applog.warn(f"Failed download of {url}")
    # change the volume?
    if settings.player_vol != settings.player_vol_default and not audiodev.broken:
      applog.info(f'set player vol to {settings.player_vol}')
      audiodev.set_volume(settings.player_vol)
    player_mp3 = True
    mp3_player(tmpf)
    player_reset()
    applog.info('tts finished')
  
# in order to kill a subprocess running mpg123 (in this case)
# we need a Popen object. I want the Shell too. 
playSiren = False
siren_obj = None

def siren_loop(fn):
  global playSiren, isDarwin, hmqtt, applog, siren_obj
  cmd = f'{audiodev.play_mp3_cmd} sirens/{fn}'
  while True:
    if playSiren == False:
      break
    siren_obj = Popen('exec ' + cmd, shell=True)
    siren_obj.wait()
    
# Restore volume if it was changed
def siren_reset():
  global settings, applog, audiodev
  if settings.siren_vol != settings.siren_vol_default and not audiodev.broken:
    applog.info(f'reset siren vol to {settings.siren_vol_default}')
    settings.siren_vol = settings.siren_vol_default
    audiodev.set_volume(settings.siren_vol_default)

def sirenCb(msg):
  global applog, hmqtt, playSiren, siren_obj, audiodev
  if msg == 'off':
    if playSiren == False:
      return
    playSiren = False
    applog.info("killing siren")
    siren_obj.terminate()
    siren_reset()
  else:
    if settings.siren_vol != settings.siren_vol_default and not audiodev.broken:
      applog.info(f'set siren vol to {settings.siren_vol}')
      audiodev.set_volume(settings.siren_vol)
    if msg == 'on':
      fn = 'Siren.mp3'
    else:
      fn = msg
    applog.info(f'play siren: {fn}')
    playSiren = True
    siren_loop(fn)
    siren_reset()
    applog.info('siren finished')


play_chime = False
chime_obj = None

def chime_mp3(fp):
  global chime_obj, applog, audiodev
  cmd = f'{audiodev.play_mp3_cmd} {fp}'
  chime_obj = Popen('exec ' + cmd, shell=True)
  chime_obj.wait()

# Restore volume if it was changed
def chime_reset():
  global settings, applog, audiodev
  if settings.chime_vol != settings.chime_vol_default and not audiodev.broken:
    applog.info(f'reset chime vol to {settings.chime_vol_default}')
    settings.chime_vol = settings.chime_vol_default
    audiodev.set_volume(settings.chime_vol_default)

def chimeCb(msg):
  global applog, chime_obj, play_chime, settings, audiodev
  if msg == 'off':
    if play_chime != True:
      return
    play_chime = False
    applog.info("killing chime")
    chime_obj.terminate()
    chime_reset()
  else:
    # if volume != volume_default, set new volume, temporary
    if settings.chime_vol != settings.chime_vol_default and not audiodev.broken:
      applog.info(f'set chime vol to {settings.chime_vol}')
      audiodev.set_volume(settings.chime_vol)
    flds = msg.split('-')
    num = int(flds[0].strip())
    nm = flds[1].strip()
    fn = 'chimes/' + nm + '.mp3'
    applog.info(f'play chime: {fn}')
    play_chime = True
    chime_mp3(fn)
    chime_reset()
    applog.info('chime finished')
  
    
# TODO: order Lasers with pan/tilt motors. Like the turrets? ;-)       
def strobeCb(msg):
  global applog, hmqtt
  applog.info(f'missing lasers for strobe {msg}, Cheapskate!')

    
def main():
  global isPi, settings, hmqtt, applog, wss_server, audiodev
  global microphone, recognizer
  # process cmdline arguments
  loglevels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
  ap = argparse.ArgumentParser()
  ap.add_argument("-c", "--conf", required=True, type=str,
    help="path and name of the json configuration file")
  ap.add_argument("-s", "--syslog", action = 'store_true',
    default=False, help="use syslog")
  args = vars(ap.parse_args())
  
  # logging setup
  # Note: websockets is very chatty at DEBUG level. Sigh.
  applog = logging.getLogger('mqttaudio')
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
  # setup pulseaudio and device volumes.
  audiodev = AudioDev()
  pulse_setup(settings)
  # The hubitat devices (player, chime, siren) can have separate
  # volumes and be restored to their defaults. The computer OS 
  # and libraries hold the real values so we read them. The OS
  # might even save them when we change them. 
  #
  # The tts device (used by the 'engine', aka mycroft or glados)
  # does not change it's volume programmatically but we have
  # coded it like it could. That tts has it's own setting.
  # A bit confusing. 
  # 
  settings.player_vol_default = audiodev.sink_volume
  settings.chime_vol_default = audiodev.sink_volume
  settings.siren_vol_default = audiodev.sink_volume
  settings.tss_vol_default = audiodev.sink_volume
  settings.player_vol = audiodev.sink_volume
  settings.chime_vol = audiodev.sink_volume
  settings.siren_vol = audiodev.sink_volume
  settings.tss_vol = settings.speaker_volume
  
  recognizer = speech_recog.Recognizer()
  microphone = speech_recog.Microphone(device_index=settings.microphone_index)

  wss_server_init(settings)
  # it doesn't do anything, no need to call it.
  #five_min_timer()   
  asyncio.get_event_loop().run_until_complete(wss_server)
  asyncio.get_event_loop().run_forever()

  # do something magic to integrate the event loops? 
  while True:
    time.sleep(5)

if __name__ == '__main__':
  sys.exit(main())

