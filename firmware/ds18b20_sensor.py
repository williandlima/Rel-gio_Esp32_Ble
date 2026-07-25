# Wrapper do sensor DS18B20 (1-Wire) usando os módulos onewire/ds18x20
# já inclusos no firmware MicroPython oficial para ESP32.

from machine import Pin
from utime import sleep_ms
import onewire
import ds18x20

VERSION = "ds18b20_sensor v1"


class DS18B20:
    def __init__(self, data_pin):
        self._ow = onewire.OneWire(Pin(data_pin))
        self._ds = ds18x20.DS18X20(self._ow)
        self._roms = self._ds.scan()
        if not self._roms:
            raise RuntimeError("Nenhum sensor DS18B20 encontrado no barramento 1-Wire")

    def read_celsius(self):
        self._ds.convert_temp()
        sleep_ms(750)  # tempo de conversão exigido pelo sensor
        return self._ds.read_temp(self._roms[0])
