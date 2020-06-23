#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Title        : MoodeAudio_OLED.py
Author       : zzeromin, member of Raspberrypi Village and Tentacle Team
Creation Date: Oct 10, 2018
Cafe         : http://cafe.naver.com/raspigamer
Blog         : http://rasplay.org, http://forums.rasplay.org/
Github       : https://github.com/zzeromin
Thanks to    : smyani and Tentacle Team
Free and open for all to use. But put credit where credit is due.
Examples of proper way to credit us : https://github.com/zzeromin/MoodeAudio-OLED

Reference    :
 https://github.com/zzeromin/RuneAudio-OLED
 https://brunch.co.kr/@gogamza/6
 https://github.com/haven-jeon/piAu_volumio
 http://blog.naver.com/kjnam100/220805352857
 https://pypi.python.org/pypi/Pillow/2.1.0
 https://github.com/adafruit/Adafruit_CircuitPython_SSD1306

Font         :
 SourceHanSansK-Normal.otf  https://github.com/adobe-fonts/source-han-sans
 neodgm.ttf  https://github.com/Dalgona/neodgm
 NanumGothic.ttf  https://github.com/naver/nanumfont
 NotoSansUI-Regular.ttf  https://github.com/google-fonts-bower/notosansui-bower

"""

import time
import os
import board
from sys import exit
from subprocess import *
from time import *
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from mpd import MPDClient, MPDError, CommandError

# Import all board pins.
from board import SCL, SDA
import busio

# Import the SSD1306 module.
import adafruit_ssd1306

# Create the I2C interface.
i2c = board.I2C()

# Create the SSD1306 OLED class.
# The first two parameters are the pixel width and pixel height.  Change these
# to the right size for your display!
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
# Alternatively you can change the I2C address of the device with an addr parameter:
#display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c, addr=0x31)

# Raspberry Pi pin configuration:
RST = 24
# Note the following are only used with SPI:
DC = 23
SPI_PORT = 0
SPI_DEVICE = 0

class PollerError(Exception):
    """Fatal error in poller."""

class MPDPoller(object):
    def __init__(self, host="localhost", port="6600", password=None):
        self._host = host
        self._port = port
        self._password = password
        self._client = MPDClient()

    def connect(self):
        try:
            self._client.connect(self._host, self._port)
        # Catch socket errors
        except IOError as err:
            errno, strerror = err
            raise PollerError("Could not connect to '%s': %s" %
                              (self._host, strerror))

        # Catch all other possible errors
        # ConnectionError and ProtocolError are always fatal.  Others may not
        # be, but we don't know how to handle them here, so treat them as if
        # they are instead of ignoring them.
        except MPDError as e:
            raise PollerError("Could not connect to '%s': %s" %
                              (self._host, e))

        if self._password:
            try:
                self._client.password(self._password)

            # Catch errors with the password command (e.g., wrong password)
            except CommandError as e:
                raise PollerError("Could not connect to '%s': "
                                  "password commmand failed: %s" %
                                  (self._host, e))

            # Catch all other possible errors
            except (MPDError, IOError) as e:
                raise PollerError("Could not connect to '%s': "
                                  "error with password command: %s" %
                                  (self._host, e))

    def disconnect(self):
        # Try to tell MPD we're closing the connection first
        try:
            self._client.close()

        # If that fails, don't worry, just ignore it and disconnect
        except (MPDError, IOError):
            pass

        try:
            self._client.disconnect()

        # Disconnecting failed, so use a new client object instead
        # This should never happen.  If it does, something is seriously broken,
        # and the client object shouldn't be trusted to be re-used.
        except (MPDError, IOError):
            self._client = MPDClient()

    def poll(self):
        try:
            song = self._client.currentsong()
            stats = self._client.status()

            if stats['state'] == 'stop':
                return(None)

            if 'artist' not in song:
                artist = song['name']
            else:
                artist = song['artist']

            if 'title' not in song:
                title = ""
            else:
                title = song['title']

            song_info = ""

            if 'audio' not in stats:
                audio = ""
            else:
                frequency = stats['audio'].split(':')[0]
                z, f = divmod(int(frequency), 1000)
                if (f == 0): frequency = str(z) + " kHz"
                else: frequency = str(float(frequency) / 1000) + "kHz"
                song_info += stats['audio'].split(':')[1] + "bit " + frequency

            bitrate = stats['bitrate']
            song_info += " " + stats['bitrate'] + "kbps"
            songplayed = stats['elapsed']
            m, s = divmod(float(songplayed), 60)
            h, m = divmod(m, 60)

            if 'volume' not in stats:
                vol = ""
            else:
                vol = stats['volume']

        # Couldn't get the current song, so try reconnecting and retrying
        except (MPDError, IOError):
            # No error handling required here
            # Our disconnect function catches all exceptions, and therefore
            # should never raise any.
            self.disconnect()

            try:
                self.connect()

            # Reconnecting failed
            except PollerError as e:
                raise PollerError("Reconnecting failed: %s" % e)

            try:
                song = self._client.currentsong()

            # Failed again, just give up
            except (MPDError, IOError) as e:
                raise PollerError("Couldn't retrieve current song: %s" % e)

        # Hurray!  We got the current song without any errors!
        eltime = "%d:%02d:%02d" % (h, m, s)
        return({'artist': artist, 'title': title, 'eltime': eltime, 'volume': vol, 'song_info': song_info})

def run_cmd(cmd):
    # runs whatever is in the cmd variable in the terminal
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def get_ip_address(cmd, cmdeth):
    # ip information
    ipaddr = run_cmd(cmdeth)

    # selection of wlan or eth address
    count = len(ipaddr)
    if count == 0:
        ipaddr = run_cmd(cmd)
    return ipaddr

def main():

    poller = MPDPoller()
    poller.connect()

    # Clear display.
    oled.fill(0)
    oled.show()

    # Create blank image for drawing.
    # Make sure to create image with mode '1' for 1-bit color.
    width = oled.width
    height = oled.height
    image = Image.new('1', (width, height))

    # Get drawing object to draw on image.
    draw = ImageDraw.Draw(image)

    # Draw a black filled box to clear the image.
    draw.rectangle((0, 0, width, height), outline=0, fill=0)

    # Draw some shapes.
    # First define some constants to allow easy resizing of shapes.
    padding = 2
    shape_width = 20
    top = padding
    bottom = height-padding
    x = padding
    # Load default font.    
    font_art = ImageFont.truetype('/home/pi/MoodeAudio-OLED/font/SourceHanSansK-Normal.otf', 12)
    font_tit = ImageFont.truetype('/home/pi/MoodeAudio-OLED/font/SourceHanSansK-Normal.otf', 12)
    font_info = ImageFont.truetype('/home/pi/MoodeAudio-OLED/font/NotoSansUI-Regular.ttf', 12)
    font_msg1 = ImageFont.truetype('/home/pi/MoodeAudio-OLED/font/neodgm.ttf', 16)
    font_msg2 = ImageFont.truetype('/home/pi/MoodeAudio-OLED/font/NanumGothic.ttf', 14)

    while True:
        draw.rectangle((0, 0, width, height), outline=0, fill=0)

        status = poller.poll()

        #get ip address of eth0 connection
        cmdeth = "ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1"
        #get ip address of wlan0 connection
        cmd = "ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1"
        #get ip address of eth0 connection
        ipaddr = get_ip_address(cmd, cmdeth)
        ip = str(ipaddr)

        if status is None:
            msg1 = "라즈뮤직파이"
            msg2 = "라즈겜동 텐타클 팀"
            msg3 = datetime.now().strftime( "%b %d %H:%M:%S" )
            msg4 = "IP " + ip[2:-3]
            t1_size = draw.textsize(msg1, font=font_msg1)
            t2_size = draw.textsize(msg2, font=font_msg2)
            t3_size = draw.textsize(msg3, font=font_info)
            t4_size = draw.textsize(msg4, font=font_info)

            draw.rectangle((0,0,width,height), outline=0, fill=0)
            draw.text(((width-t1_size[0])/2, top), msg1, font=font_msg1, fill=255)
            draw.text(((width-110)/2, top+18), msg2, font=font_msg2, fill=255)
            draw.text(((width-t3_size[0])/2, top+34), msg3, font=font_info, fill=255)
            draw.text(((width-t4_size[0])/2, top+48), msg4, font=font_info, fill=255)
            oled.image(image)
            oled.show()
            continue

        artist = status['artist']
        title = status['title']
        eltime = status['eltime']
        song_info = status['song_info']

        if 'volume' not in status:
            vol = ""
        else:
            vol = status['volume']

        #print (titleLength, txtFind.isalpha())
        title = title

        titleLength = len(title)
        if titleLength > 0:
            txtFind = title[0]
            if txtFind.isalpha():
                titleLine3 = 40
                titleLine2 = 22
                titleIndex1 = 14
                titleIndex2 = 38
            else:
                titleLine3 = 60
                titleLine2 = 24
                titleIndex1 = 16
                titleIndex2 = 40

            if titleLength > titleLine3:
                draw.text((0, top), artist, font=font_art, fill=255)
                draw.text((0, top+15), title[0:titleIndex1], font=font_tit, fill=255)
                draw.text((0, top+30), title[titleIndex1:titleIndex2], font=font_tit, fill=255)
                draw.text((0, top+45), title[titleIndex2:60], font=font_tit, fill=255)

            elif titleLength > titleLine2:
                draw.text((0, top), artist, font=font_art, fill=255)
                draw.text((0, top+15), title[0:titleIndex1], font=font_tit, fill=255)
                draw.text((0, top+30), title[titleIndex1:titleIndex2], font=font_tit, fill=255)
                draw.text((0, top+45), eltime, font=font_info, fill=255)
                draw.text((88, top+45), "Vol " + str(vol), font=font_info, fill=255)

            else:
                draw.text((0, top), artist, font=font_art, fill=255)
                draw.text((0, top+15), title, font=font_tit, fill=255)
                draw.text((0, top+30), eltime, font=font_info, fill=255)
                draw.text((88, top+30), "Vol " + str(vol), font=font_info, fill=255)
                draw.text((0, top+45), song_info, font=font_info, fill=255)

        else:
            artist = "no information"
            title = "Internet Radio"
            draw.text((0, top), artist, font=font_art, fill=255)
            draw.text((0, top+15), title, font=font_tit, fill=255)
            draw.text((0, top+30), eltime, font=font_info, fill=255)
            draw.text((88, top+30), "Vol " + str(vol), font=font_info, fill=255)
            draw.text((0, top+45), song_info, font=font_info, fill=255)

        oled.image(image)
        oled.show()
        sleep(1)

if __name__ == "__main__":
    import sys

    try:
        main()

    # Catch fatal poller errors
    except PollerError as e:
        sys.stderr.write("Fatal poller error: %s" % e)
        sys.exit(1)

    # Catch all other non-exit errors
    except Exception as e:
        sys.stderr.write("Unexpected exception: %s" % e)
        sys.exit(1)

    # Catch the remaining exit errors
    except:
        sys.exit(0)
