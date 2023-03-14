# Bridge for Trumpybear and Mycroft

Using mqtt, trumpybear communicates to the bridge. The bridge will then
poke mycroft via it's 'message bus' port/api

2023-Mar-13
1. import pulsectl
2. trumpy.json - include pulseaudio sink/source (speaker/mic) names and 
volumes.
3. Set the pulseaudio sink/source to the given device names
4. Use pulseaudio api to mute/unmute pulseaudio (and effectively, mycroft)
   Unknown if that fixes mycroft waking up sometimes for no known reason.
   Since we mute the speaker and the mic - we won't hear it if it does
   wake up.

Still have to determine if the mycroft site is working.
