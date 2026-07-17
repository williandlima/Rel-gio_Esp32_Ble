# Versão temporária do Modo Normal SEM o RTC DS3231 — usa o relógio
# interno do ESP32 (machine.RTC) só pra testar LCD + DS18B20 enquanto o
# DS3231 não está respondendo no I2C.
#
# Atenção: o RTC interno do ESP32 NÃO tem bateria — perde a hora toda vez
# que a placa é desligada/resetada. É só um substituto temporário; quando
# o DS3231 estiver funcionando, volte a usar test_normal_mode.py.

from machine import RTC, Pin
from utime import sleep

from lcd_hd44780 import LCD4Bit
from ds18b20_sensor import DS18B20
import config

WEEKDAYS = ("", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")

# ---- EDITE AQUI (data/hora atual) ----
ANO, MES, DIA = 2026, 7, 17
DIA_DA_SEMANA = 5  # 1=Segunda ... 7=Domingo
HORA, MINUTO, SEGUNDO = 13, 30, 0
# ---------------------------------------

rtc = RTC()
rtc.datetime((ANO, MES, DIA, DIA_DA_SEMANA, HORA, MINUTO, SEGUNDO, 0))

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

temp_sensor = DS18B20(config.ONEWIRE_DATA)

TEMP_REFRESH_CYCLES = 5
cycle = 0
temp_c = temp_sensor.read_celsius()

while True:
    year, month, day, weekday, hour, minute, second, _ = rtc.datetime()

    if cycle % TEMP_REFRESH_CYCLES == 0:
        temp_c = temp_sensor.read_celsius()
    cycle += 1

    date_str = "{}, {:02d}/{:02d}/{:04d}".format(WEEKDAYS[weekday], day, month, year)
    time_str = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
    temp_str = "Temp: {:.1f} C".format(temp_c)

    lcd.write_line(date_str, row=0)
    lcd.write_line(time_str, row=1)
    lcd.write_line(temp_str, row=2)
    lcd.write_line("Sem RTC (temp only)", row=3)

    sleep(1)
