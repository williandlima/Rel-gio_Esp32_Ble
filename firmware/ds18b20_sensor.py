# Wrapper do sensor DS18B20 (1-Wire) usando os módulos onewire/ds18x20
# já inclusos no firmware MicroPython oficial para ESP32.
#
# A leitura é dividida em duas etapas — start_conversion() e read_result() —
# porque o sensor exige ~750ms de conversão. Esperar esse tempo dentro do
# laço principal fazia o relógio congelar e pular segundos no display a
# cada atualização de temperatura.
#
# Nenhum método levanta exceção por falha do sensor: um DS18B20 ausente ou
# com erro de CRC não pode derrubar o relógio inteiro.

from machine import Pin
from micropython import const
from utime import sleep_ms, ticks_ms, ticks_diff
import onewire
import ds18x20

VERSION = "ds18b20_sensor v2 (leitura nao-bloqueante)"

_CONVERSION_MS = const(750)


class DS18B20:
    def __init__(self, data_pin):
        self._ow = onewire.OneWire(Pin(data_pin))
        self._ds = ds18x20.DS18X20(self._ow)
        self._roms = []
        self._conversion_started = None
        self.rescan()

    def rescan(self):
        """Procura sensores no barramento. Retorna True se achou algum."""
        try:
            self._roms = self._ds.scan()
        except Exception as e:
            print("Falha ao varrer o barramento 1-Wire:", e)
            self._roms = []
        return self.available

    @property
    def available(self):
        return len(self._roms) > 0

    @property
    def conversion_pending(self):
        return self._conversion_started is not None

    def start_conversion(self):
        """Dispara a conversão e retorna imediatamente."""
        if not self._roms:
            return False
        try:
            self._ds.convert_temp()
        except Exception as e:
            print("Falha ao iniciar conversao do DS18B20:", e)
            self._conversion_started = None
            return False
        self._conversion_started = ticks_ms()
        return True

    def result_ready(self):
        if self._conversion_started is None:
            return False
        return ticks_diff(ticks_ms(), self._conversion_started) >= _CONVERSION_MS

    def read_result(self):
        """Lê o resultado da conversão. Retorna °C ou None em caso de falha."""
        self._conversion_started = None
        if not self._roms:
            return None
        try:
            return self._ds.read_temp(self._roms[0])
        except Exception as e:
            print("Falha ao ler o DS18B20:", e)
            return None

    def read_celsius(self):
        """Leitura bloqueante (~750ms), por conveniência em testes no REPL.
        O laço principal usa a versão em duas etapas."""
        if not self.start_conversion():
            return None
        sleep_ms(_CONVERSION_MS)
        return self.read_result()
