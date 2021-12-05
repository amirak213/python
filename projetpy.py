import machine
from machine import Pin
import network  # Connexion Wifi dans le script
import sys
import json
from umqtt.simple import MQTTClient
import ubinascii

class HCSR04:
    """
    Driver to use the untrasonic sensor HC-SR04.
    The sensor range is between 2cm and 4m.
    The timeouts received listening to echo pin are converted to OSError('Out of range')
    """
    # echo_timeout_us is based in chip range limit (400cm)
    def __init__(self, trigger_pin, echo_pin, echo_timeout_us=500*2*30):
        """
        trigger_pin: Output pin to send pulses
        echo_pin: Readonly pin to measure the distance. The pin should be protected with 1k resistor
        echo_timeout_us: Timeout in microseconds to listen to echo pin.
        By default is based in sensor limit range (4m)
        """
        self.__version__ = '0.2.0'
        self.__author__ = 'Roberto Sánchez'
        self.__license__ = "Apache License 2.0. https://www.apache.org/licenses/LICENSE-2.0"

        self.echo_timeout_us = echo_timeout_us
        # Init trigger pin (out)
        self.trigger = Pin(trigger_pin, mode=Pin.OUT, pull=None)
        self.trigger.value(0)

        # Init echo pin (in)
        self.echo = Pin(echo_pin, mode=Pin.IN, pull=None)

    def _send_pulse_and_wait(self):
        """
        Send the pulse to trigger and listen on echo pin.
        We use the method `machine.time_pulse_us()` to get the microseconds until the echo is received.
        """
        self.trigger.value(0) # Stabilize the sensor
        time.sleep_us(5)
        self.trigger.value(1)
        # Send a 10us pulse.
        time.sleep_us(10)
        self.trigger.value(0)
        try:
            pulse_time = machine.time_pulse_us(self.echo, 1, self.echo_timeout_us)
            return pulse_time
        except OSError as ex:
            if ex.args[0] == 110: # 110 = ETIMEDOUT
                raise OSError('Out of range')
            raise ex

    def distance_mm(self):
        """
        Get the distance in milimeters without floating point operations.
        """
        pulse_time = self._send_pulse_and_wait()

        # To calculate the distance we get the pulse_time and divide it by 2
        # (the pulse walk the distance twice) and by 29.1 becasue
        # the sound speed on air (343.2 m/s), that It's equivalent to
        # 0.34320 mm/us that is 1mm each 2.91us
        # pulse_time // 2 // 2.91 -> pulse_time // 5.82 -> pulse_time * 100 // 582
        mm = pulse_time * 100 // 582
        return mm

    def distance_cm(self):
        """
        Get the distance in centimeters with floating point operations.
        It returns a float
        """
        pulse_time = self._send_pulse_and_wait()

        # To calculate the distance we get the pulse_time and divide it by 2
        # (the pulse walk the distance twice) and by 29.1 becasue
        # the sound speed on air (343.2 m/s), that It's equivalent to
        # 0.034320 cm/us that is 1cm each 29.1us
        cms = (pulse_time / 2) / 29.1
        return cms

############################
# Debut configuration Wifi #
############################
WIFI_SSID = "XXX"
WIFI_PASSWORD = "XXX"

# turn off the WiFi Access Point
ap_if = network.WLAN(network.AP_IF)
ap_if.active(False)

# connect the device to the WiFi network
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(WIFI_SSID, WIFI_PASSWORD)

# wait until the device is connected to the WiFi network
MAX_ATTEMPTS = 20
attempt_count = 0
while not wifi.isconnected() and attempt_count < MAX_ATTEMPTS:
    attempt_count += 1
    time.sleep(1)

if attempt_count == MAX_ATTEMPTS:
    print("could not connect to the WiFi network")
    sys.exit()

################################
# fin de la configuration Wifi #
################################

# parametres MQTTClient
AIO_SERVER = "io.adafruit.com"
AIO_USER = "XXX"
AIO_APIKEY = "XXX"
AIO_FEED = "XXX"
CLIENT_ID = ubinascii.hexlify(machine.unique_id())

client = MQTTClient(
    client_id=CLIENT_ID,
    server=AIO_SERVER,
    user=AIO_USER,
    password=AIO_APIKEY,
    ssl=False,
)
mqtt_feedname = "{:s}/feeds/{:s}".format(AIO_USER, AIO_FEED)

try:
    client.connect()
except Exception as e:
    print("Connexion au serveur MQTT impossible : {}{}".format(type(e).__name__, e))
    sys.exit()

# GPIO 5 <-> D1 / GPIO 4 <-> D2
sensor = HCSR04(trigger_pin=5, echo_pin=4)

while True:
    distance = sensor.distance_cm() - 5 # le capteur est à 5cm au desssus du niveau du puisard
    print('Distance:', distance, 'cm')
    client.publish(mqtt_feedname, str(distance))
    time.sleep_ms(60000)
