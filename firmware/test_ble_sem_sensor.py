# Variante temporária do teste BLE (etapa 3) SEM o sensor DS18B20 — útil
# para testar Display + RTC interno + BLE quando o sensor de temperatura
# não estiver conectado. A temperatura continua no escopo do projeto
# (ver SPECS.md); este arquivo é só uma conveniência de teste.
#
# Use um app BLE genérico (ex: nRF Connect) ou o app Android pra:
#   - Escrever em SetDateTime: {"epoch": 1752500000}  (epoch Unix, segundos
#     desde 1970) -> ajusta o RTC interno na hora.
#   - Escrever em Marquee: {"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}
#     -> por enquanto só aparece no Shell (comportamento real é a etapa 5).
#   - Ler/escrever em Config: {"temp_unit": "C"}
#   - Ler/assinar notificações em Status: {"mode": "normal", "connected": ...}
#     (sem "temp_c" nesta variante, já que não há sensor conectado)

from machine import RTC
from utime import sleep, localtime

from lcd_hd44780 import LCD4Bit
from ble_service import ClockBLEService
import config

WEEKDAYS = ("", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")

# Diferença, em segundos, entre a época Unix (1970-01-01) e a época usada
# pelo MicroPython no ESP32 (2000-01-01) — necessária para converter o
# "epoch" recebido do app (Unix) para o formato que o RTC espera.
_UNIX_TO_MPY_EPOCH_OFFSET = 946684800

rtc = RTC()

lcd = LCD4Bit(
    rs_pin=config.LCD_RS,
    e_pin=config.LCD_E,
    d4_pin=config.LCD_D4,
    d5_pin=config.LCD_D5,
    d6_pin=config.LCD_D6,
    d7_pin=config.LCD_D7,
    cols=config.LCD_COLS,
    rows=config.LCD_ROWS,
)


def handle_set_datetime(data):
    unix_epoch = data.get("epoch")
    if unix_epoch is None:
        return
    year, month, day, hour, minute, second, wday0, _yday = localtime(
        unix_epoch - _UNIX_TO_MPY_EPOCH_OFFSET
    )
    weekday = wday0 + 1  # localtime: 0=Segunda -> nosso padrão: 1=Segunda
    rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
    print("SetDateTime recebido, RTC ajustado:", rtc.datetime())


def handle_marquee(data):
    # Comportamento real (scroll + duração) é a etapa 5 do roadmap.
    print("Marquee recebido:", data)


def handle_config_write(data):
    print("Config recebido:", data)


ble = ClockBLEService(name="Relogio-ESP32")
ble.on_set_datetime = handle_set_datetime
ble.on_marquee = handle_marquee
ble.on_config_write = handle_config_write
ble.set_config({"temp_unit": "C"})

STATUS_REFRESH_CYCLES = 5
cycle = 0

while True:
    year, month, day, weekday, hour, minute, second, _ = rtc.datetime()

    if cycle % STATUS_REFRESH_CYCLES == 0:
        ble.set_status({
            "mode": "normal",
            "connected": ble.is_connected(),
        })
    cycle += 1

    date_str = "{}, {:02d}/{:02d}/{:04d}".format(WEEKDAYS[weekday], day, month, year)
    time_str = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)

    lcd.write_line(date_str, row=0)
    lcd.write_line(time_str, row=1)
    lcd.write_line("Sem sensor de temp.", row=2)
    lcd.write_line("Relogio ESP32 BLE", row=3)

    sleep(1)
