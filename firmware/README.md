# Firmware — Relogio_Esp32_Ble (MicroPython)

## Como testar o display (etapa 1 do roadmap)

1. No Thonny: `Ferramentas > Opções > Interpretador`, selecione
   "MicroPython (ESP32)" e a porta serial do ESP32 (com o firmware
   MicroPython já gravado).
2. Faça upload dos arquivos para o ESP32 (View > Files, arrasta para o
   dispositivo): `config.py`, `lcd_hd44780.py`, `test_display.py`.
3. Abra `test_display.py` no Thonny e rode com F5.
4. Resultado esperado no display (20x4):

   ```
   Ter, 14/07/2026
   14:32:07
   Temp: 24.5 C
   Relogio ESP32 BLE
   ```

Se o texto não aparecer, ajuste o potenciômetro de contraste (pino Vo)
antes de suspeitar do código/fiação.

## Como testar RTC + temperatura (etapa 2 do roadmap)

Requer o DS3231 (I2C) e o DS18B20 (1-Wire) já ligados conforme `config.py` /
`SPECS.md` seção 2.2 (SDA=21, SCL=22, DS18B20 DATA=4 com pull-up 4.7kΩ).

1. Suba os arquivos: `config.py`, `lcd_hd44780.py`, `rtc_ds3231.py`,
   `ds18b20_sensor.py`, `set_rtc_time.py`, `test_normal_mode.py`.
2. Abra `set_rtc_time.py`, edite a data/hora atual no topo do arquivo e
   rode com **F5** uma única vez (isso grava a hora no DS3231, que a
   mantém sozinho depois graças à bateria própria).
3. Abra `test_normal_mode.py` e rode com **F5**.
4. Esperado no display, atualizando a cada segundo:
   ```
   Sex, 17/07/2026
   14:30:05
   Temp: 24.5 C
   Relogio ESP32 BLE
   ```

## Pinagem usada (ver `config.py` / `SPECS.md` seção 2.2)

| Sinal | GPIO |
|---|---|
| LCD RS | 13 |
| LCD E | 14 |
| LCD D4-D7 | 27, 26, 25, 33 |
| I2C SDA / SCL (DS3231) | 21 / 22 |
| DS18B20 DATA | 4 |
