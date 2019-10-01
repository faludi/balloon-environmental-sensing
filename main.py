# This program sends Pysense sensor board data to The Things Network (TTN)
# every 30 seconds at the second slowest data rate for the U.S.
# Created with help from multiple online examples
# by Rob Faludi, faludi.com

from network import LoRa
import socket
import time
import ubinascii
import pycom
from pysense import Pycoproc # battery and button module
import cayenneLPP  # https://github.com/jojo-/py-cayenne-lpp/
from machine import Timer
# sensor modules
from MPL3115A2 import MPL3115A2
from SI7006A20 import SI7006A20
from LTR329ALS01 import LTR329ALS01
from LIS2HH12 import LIS2HH12

# name and version to console
print('Pysense-TTN')
print('LoPy4')

# initialize sensors
acc = LIS2HH12()
baro = MPL3115A2(mode=0) # mode 0 for altitude, mode 1 for pressure
light = LTR329ALS01()
temphumid = SI7006A20()
pc = Pycoproc()

# Initialise LoRa in LORAWAN mode with region:
# Asia = LoRa.AS923, Australia = LoRa.AU915, Europe = LoRa.EU868,
# United States = LoRa.US915
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.US915)

# remove unused channels in U.S.
for index in range(0, 8):
    lora.remove_channel(index)
for index in range(16, 65):
    lora.remove_channel(index)
for index in range(66, 72):
    lora.remove_channel(index)

# create an OTAA authentication parameters
app_eui = ubinascii.unhexlify('70B3D57ED001FACD')
app_key = ubinascii.unhexlify('EF37EB4214BF4857D048AE79D83B149C')

# join a network using OTAA (Over the Air Activation)
lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)

# wait until the module has joined the network, showing indicator LED
while not lora.has_joined():
    pycom.heartbeat(False) # blue blinking off
    time.sleep(2.5)
    pycom.rgbled(0xFFFF00) # yellow
    time.sleep(0.2)
    pycom.rgbled(0x000000) # led off
    print('Not yet joined...')
pycom.heartbeat(True) # blue blinking back on

# create a LoRa socket
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# set the LoRaWAN data rate
# list of data rates: https://blog.dbrgn.ch/2017/6/23/lorawan-data-rates/
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 1)

# a timed alarm sends data periodically
class Sender:
    def __init__(self):
        print('starting timer...')
        # send an immediate data payload
        self.__alarm = Timer.Alarm(self._send_handler, 1, periodic=False)
        # send a periodic data payload
        self.__alarm = Timer.Alarm(self._send_handler, 30, periodic=True)
        self.counter = 0

    def _send_handler(self, alarm):
        print('sending...')
        # creating Cayenne LPP packet
        lpp = cayenneLPP.CayenneLPP(size = 60, sock = s) # adjust payload size if needed
        # take measurements
        pitch = acc.pitch()
        roll = acc.roll()
        accel = acc.acceleration()
        # pressure = baro.pressure()
        altitude = baro.altitude()
        barotemp = baro.temperature()
        levels = light.light()
        # temp = temphumid.temperature()
        humid = temphumid.humidity()
        battery = pc.read_battery_voltage()
        self.counter = self.counter + 1  # simple counter for logging

        # show measurements
        print('pitch:', pitch)
        print('roll:', roll)
        print('baro temp:', barotemp)
        print('acceleration: x {},  y {},  z {}'.format(accel[0], accel[1], accel[2]))
        print('altitude:', altitude)
        # print('pressure:', pressure/100)
        print('light avg:', (levels[0]+levels[1]) / 2)
        # print('temp:', temp)
        print('humid:', humid)
        print('battery', battery)
        print('counter', self.counter)

        # send measurements
        lpp.add_analog_input(pitch)
        lpp.add_analog_input(roll, channel=103)
        lpp.add_temperature(barotemp, channel=107)
        lpp.add_accelerometer(accel[0], accel[1], accel[2], )
        # lpp.add_barometric_pressure(pressure/100) # convert pa to Hectopascals
        lpp.add_analog_input(altitude, channel=104)
        lpp.add_luminosity( (levels[0]+levels[1]) / 2)
        # lpp.add_temperature(temp)
        lpp.add_relative_humidity(humid)
        lpp.add_analog_input(battery, channel = 105)
        lpp.add_analog_input(self.counter, channel = 106)
        print('payload size: {}'.format(lpp.get_size())) # show payload get_size
        # if payload is too large, adjust in Sender._send_handler above if needed

        # sending the packet via the socket
        try:
            lpp.send()
        except OSError as e:
            print(e)
            pycom.heartbeat(False)
            for x in range(10):
                pycom.rgbled(0xFF0000) # red blinking for errors
                time.sleep(0.2)
                pycom.rgbled(0x000000) # off
                time.sleep(0.2)
            import machine
            machine.reset()
        pycom.heartbeat(False)
        pycom.rgbled(0x00FF00) # green flash for success
        time.sleep(0.2)
        pycom.heartbeat(True)
        if pc.button_pressed(): # holding button cancels data sending until reboot
            self.__alarm.cancel()
            pycom.heartbeat(False)
            pycom.rgbled(0xFF0000) # red
            time.sleep(5)
            pycom.rgbled(0x000000) # off

# start periodic data sending (using alarm function)
sender = Sender()
