# Driver mínimo para o RTC DS3231 (I2C) em MicroPython.

_DS3231_ADDR = 0x68


def _bcd2dec(bcd):
    return (bcd >> 4) * 10 + (bcd & 0x0F)


def _dec2bcd(dec):
    return ((dec // 10) << 4) | (dec % 10)


class DS3231:
    def __init__(self, i2c):
        self.i2c = i2c

    def get_datetime(self):
        # Retorna (ano, mes, dia, dia_da_semana[1-7, 1=Segunda], hora, minuto, segundo)
        data = self.i2c.readfrom_mem(_DS3231_ADDR, 0x00, 7)
        second = _bcd2dec(data[0] & 0x7F)
        minute = _bcd2dec(data[1])
        hour = _bcd2dec(data[2] & 0x3F)  # registrador em modo 24h
        weekday = _bcd2dec(data[3])
        day = _bcd2dec(data[4])
        month = _bcd2dec(data[5] & 0x1F)
        year = 2000 + _bcd2dec(data[6])
        return (year, month, day, weekday, hour, minute, second)

    def set_datetime(self, year, month, day, weekday, hour, minute, second):
        data = bytes([
            _dec2bcd(second),
            _dec2bcd(minute),
            _dec2bcd(hour),
            _dec2bcd(weekday),
            _dec2bcd(day),
            _dec2bcd(month),
            _dec2bcd(year - 2000),
        ])
        self.i2c.writeto_mem(_DS3231_ADDR, 0x00, data)
