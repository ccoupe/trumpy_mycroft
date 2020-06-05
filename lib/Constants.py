import enum 

class State(enum.Enum): 
  starting = 0
  getname = 1
  waitfr = 2
  waitsd = 3
  insult = 4
  mycroft = 5
  rasa = 6
  alarm = 7

class Event(enum.Enum):
  start = 0
  reply = 1
  frpict = 2
  sdpict = 3
  recog = 4
  timer5s = 5
  timer5m = 6
