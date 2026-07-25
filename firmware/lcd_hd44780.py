# Driver HD44780 (paralelo, modo 4 bits) para MicroPython / ESP32
# Testado com display NHD-0420E2Z-NSW-BBW (20 colunas x 4 linhas)
#
# RW é fixado em GND no hardware (só escrita), por isso não é controlado aqui.

from machine import Pin
from utime import sleep_us, sleep_ms

VERSION = "lcd_hd44780 v3 (cache de linha + CGRAM)"

_LCD_CLEAR = 0x01
_LCD_HOME = 0x02
_LCD_ENTRY_MODE = 0x06          # incrementa cursor, sem shift do display
_LCD_DISPLAY_ON = 0x0C          # display on, cursor off, blink off
_LCD_FUNCTION_SET_4BIT = 0x28   # 4 bits, 2 linhas (N=1), fonte 5x8
_LCD_SET_DDRAM_ADDR = 0x80
_LCD_SET_CGRAM_ADDR = 0x40

# Endereços iniciais de cada linha, padrão para displays 20x4 (controlador
# HD44780 só endereça 2 "linhas" internamente; linhas 3 e 4 usam offset).
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

        # Última linha escrita em cada row, para não regravar conteúdo
        # idêntico: o barramento é bit-bang em 4 bits e escrever as 4
        # linhas custa ~8ms. Com o cache, só a linha da hora é reescrita a
        # cada segundo.
        self._line_cache = [None] * rows

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
        sleep_ms(20)  # aguarda estabilização da alimentação do display

        # Sequência de reset especial (datasheet HD44780): força o
        # controlador, que liga em modo 8 bits, a entrar em modo 4 bits.
        self._write_nibble(0x03)
        sleep_ms(5)
        self._write_nibble(0x03)
        sleep_us(150)
        self._write_nibble(0x03)
        sleep_us(150)
        self._write_nibble(0x02)  # agora em modo 4 bits
        sleep_us(150)

        self._command(_LCD_FUNCTION_SET_4BIT)
        self._command(_LCD_DISPLAY_ON)
        self.clear()
        self._command(_LCD_ENTRY_MODE)

    def clear(self):
        self._command(_LCD_CLEAR)
        sleep_ms(2)  # comando de clear é mais lento
        self._line_cache = [None] * self.rows

    def create_char(self, index, bitmap):
        """Grava um caractere próprio na CGRAM (índices 0..7).

        `bitmap` são 8 inteiros de 5 bits, de cima para baixo. Serve para não
        depender de posições da ROM de caracteres, que variam entre variantes
        do controlador — o bloco cheio usado pelo letreiro ampliado, por
        exemplo, não está no mesmo lugar em todas elas.
        """
        index &= 0x07
        self._command(_LCD_SET_CGRAM_ADDR | (index << 3))
        for line in bitmap:
            self._write_byte(line & 0x1F, rs=1)
        # Volta o endereçamento para a DDRAM, senão a próxima escrita cairia
        # na CGRAM em vez de na tela.
        self._command(_LCD_SET_DDRAM_ADDR)
        self._line_cache = [None] * self.rows

    def move_to(self, col, row):
        row = min(row, self.rows - 1)
        addr = _ROW_OFFSETS[row] + col
        self._command(_LCD_SET_DDRAM_ADDR | addr)

    def putstr(self, text, col=0, row=0):
        row = min(max(row, 0), self.rows - 1)
        self.move_to(col, row)
        for ch in text[: self.cols - col]:
            self._write_char(ch)
        # Escrita parcial/arbitrária: o cache da linha deixa de ser confiável.
        self._line_cache[row] = None

    def write_line(self, text, row, force=False):
        # Escreve a linha inteira, preenchendo com espaços para apagar
        # qualquer resíduo de conteúdo anterior mais longo.
        # (preenchimento manual: MicroPython não tem str.ljust())
        row = min(max(row, 0), self.rows - 1)
        truncated = text[: self.cols]
        line = truncated + " " * (self.cols - len(truncated))
        if not force and self._line_cache[row] == line:
            return
        self.putstr(line, col=0, row=row)
        self._line_cache[row] = line
