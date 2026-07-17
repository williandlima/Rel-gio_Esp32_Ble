# Ponto de entrada autônomo: MicroPython roda "main.py" sozinho toda vez
# que o ESP32 recebe energia (USB na tomada/carregador/power bank), sem
# precisar do Thonny nem de computador conectado.
#
# Como o RTC interno do ESP32 não tem bateria, a data/hora abaixo é
# aplicada de novo a cada ligada/reset. Edite os valores e reenvie este
# arquivo via Thonny sempre que quiser corrigir a hora (futuramente isso
# será feito pelo app Android via BLE, sem precisar editar nada aqui).

from machine import RTC
from utime import sleep

from lcd_hd44780 import LCD4Bit
from ds18b20_sensor import DS18B20
import config

WEEKDAYS = ("", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")

# ---- EDITE AQUI antes de gravar (data/hora no momento em que for ligar) ----
ANO, MES, DIA = 2026, 7, 17
DIA_DA_SEMANA = 5  # 1=Segunda ... 7=Domingo
HORA, MINUTO, SEGUNDO = 13, 30, 0
# -----------------------------------------------------------------------------

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
    lcd.write_line("Relogio ESP32 BLE", row=3)

    sleep(1)
