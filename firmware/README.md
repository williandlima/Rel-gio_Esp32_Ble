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

## Pinagem usada (ver `config.py` / `SPECS.md` seção 2.2)

| Sinal | GPIO |
|---|---|
| LCD RS | 13 |
| LCD E | 14 |
| LCD D4-D7 | 27, 26, 25, 33 |
