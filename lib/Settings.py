#!/usr/bin/env python3
import json
import socket
from uuid import getnode as get_mac
import os 
import sys

class Settings:

  def __init__(self, etcf, log):
    self.etcfname = etcf
    self.log = log
    self.load_settings(self.etcfname)
    self.log.info("Settings from %s" % self.etcfname)
    
  def load_settings(self, fn):
    conf = json.load(open(fn))
    self.mqtt_server_ip = conf.get("mqtt_server_ip", "192.168.1.7")
    self.mqtt_port = conf.get("mqtt_port", 1883)
    self.mqtt_client_name = conf.get("mqtt_client_name", "trumpy_bridge")
    self.homie_device = conf.get('homie_device', 'trumpy_cam')
    self.pulse = None
    self.microphone = conf.get('microphone', None)
    self.microphone_volume = conf.get('microphone_volume', 0.5)
    self.microphone_index = None
    self.mic = None
    self.speaker = conf.get('speaker', None)
    self.speaker_volume = conf.get('speaker_volume', 0.5)
    self.speaker_index = None
    self.spkr = None
    self.bridge_ip = conf.get('bridge_ip', '192.168.1.2')
    self.bridge_port = conf.get('bridge_port', 8281)
    # its required that the bridge runs on the mycroft device
    self.mycroft_uri = 'ws://' + self.bridge_ip + ':8181/core'


  def print(self):
    self.log.info("==== Settings ====")
    self.log.info(self.settings_serialize())
  
  def settings_serialize(self):
    st = {}
    st['mqtt_server_ip'] = self.mqtt_server_ip
    st['mqtt_port'] = self.mqtt_port
    st['mqtt_client_name'] = self.mqtt_client_name
    st['homie_device'] = self.homie_device 
    st['bridge_ip'] = self.bridge_ip
    st['bridge_port'] = self.bridge_port
    st['mycroft_uri'] = self.mycroft_uri
    str = json.dumps(st)
    return str

  def settings_deserialize(self, jsonstr):
    st = json.loads(jsonstr)
