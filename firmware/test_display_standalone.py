# Teste do display em arquivo único (tudo-em-um), para rodar no Thonny com
# F5. Sem dependências de outros arquivos — só isso e mais nada precisa
# estar no ESP32 para este teste.
#
# Pinagem (ver SPECS.md secao 2.2):
#   RS=13  E=14  D4=27  D5=26  D6=25  D7=33

from machine import Pin
from utime import sleep_us, sleep_ms

_LCD_CLEAR = 0x01
_LCD_ENTRY_MODE = 0x06
_LCD_DISPLAY_ON = 0x0C
_LCD_FUNCTION_SET_4BIT = 0x28
_LCD_SET_DDRAM_ADDR = 0x80
_ROW_OFFSETS = (0x00, 0x40, 0x14, 0x54)


class LCD4Bit:
    def __init__(self, rs_pin, e_pin, d4_pin, d5_pin, d6_pin, d7_pin,
                 cols=20, rows=4):
        self.cols = cols
        self.rows = rows
        self._rs = Pin(rs_pin, Pin.OUT, value=0)
        self._e = Pin(e_pin, Pin.OUT, value=0)
        self._data = [Pin(p, Pin.OUT, value=0)
                      for p in (d4_pin, d5_pin, d6_pin, d7_pin)]
        self._init_display()

    def _pulse_enable(self):
        self._e.value(0)
        sleep_us(1)
        self._e.value(1)
        sleep_us(1)
        self._e.value(0)
        sleep_us(50)

    def _write_nibble(self, nibble):
        for i in range(4):
            self._data[i].value((nibble >> i) & 0x01)
        self._pulse_enable()

    def _write_byte(self, value, rs):
        self._rs.value(rs)
        self._write_nibble((value >> 4) & 0x0F)
        self._write_nibble(value & 0x0F)

    def _command(self, cmd):
        self._write_byte(cmd, rs=0)

    def _write_char(self, ch):
        self._write_byte(ord(ch), rs=1)

    def _init_display(self):
        sleep_ms(20)
        self._write_nibble(0x03)
        sleep_ms(5)
        self._write_nibble(0x03)
        sleep_us(150)
        self._write_nibble(0x03)
        sleep_us(150)
        self._write_nibble(0x02)
        sleep_us(150)
        self._command(_LCD_FUNCTION_SET_4BIT)
        self._command(_LCD_DISPLAY_ON)
        self.clear()
        self._command(_LCD_ENTRY_MODE)

    def clear(self):
        self._command(_LCD_CLEAR)
        sleep_ms(2)

    def move_to(self, col, row):
        row = min(row, self.rows - 1)
        addr = _ROW_OFFSETS[row] + col
        self._command(_LCD_SET_DDRAM_ADDR | addr)

    def putstr(self, text, col=0, row=0):
        self.move_to(col, row)
        for ch in text[: self.cols - col]:
            self._write_char(ch)

    def write_line(self, text, row):
        # preenchimento manual: MicroPython não tem str.ljust()
        truncated = text[: self.cols]
        line = truncated + " " * (self.cols - len(truncated))
        self.putstr(line, col=0, row=row)


# ---- Teste ----
lcd = LCD4Bit(rs_pin=13, e_pin=14, d4_pin=27, d5_pin=26, d6_pin=25, d7_pin=33,
              cols=20, rows=4)

lcd.write_line("Ter, 14/07/2026", row=0)
lcd.write_line("14:32:07", row=1)
lcd.write_line("Temp: 24.5 C", row=2)
lcd.write_line("Relogio ESP32 BLE", row=3)
