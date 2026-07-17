# Teste do Modo Normal completo: LCD + RTC interno do ESP32 + DS18B20.
# Pré-requisito: já ter rodado set_time.py uma vez para acertar a hora
# (o RTC interno perde a hora ao reiniciar/desligar — reajuste quando precisar).
#
# Arquivos necessários no ESP32: config.py, lcd_hd44780.py, ds18b20_sensor.py,
# test_normal_mode.py

from machine import RTC
from utime import sleep

from lcd_hd44780 import LCD4Bit
from ds18b20_sensor import DS18B20
import config

WEEKDAYS = ("", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")

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

temp_sensor = DS18B20(config.ONEWIRE_DATA)

# A leitura do DS18B20 leva ~750ms (tempo de conversão do sensor), por isso
# só atualizamos a temperatura a cada N ciclos, não a cada segundo.
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
    lcd.write_line("Relogio ESP32 BLE", row=3)

    sleep(1)
