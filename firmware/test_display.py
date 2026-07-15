# Teste manual do display, para rodar via Thonny (F5) com o ESP32 conectado.
# Objetivo: validar fiação, contraste e o driver LCD4Bit antes de integrar
# RTC/sensor/BLE.

from lcd_hd44780 import LCD4Bit
import config

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

lcd.write_line("Ter, 14/07/2026", row=0)
lcd.write_line("14:32:07", row=1)
lcd.write_line("Temp: 24.5 C", row=2)
lcd.write_line("Relogio ESP32 BLE", row=3)
