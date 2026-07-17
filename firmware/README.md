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

Sem RTC externo — usa o **RTC interno do ESP32** (perde a hora ao
desligar/resetar, precisa reajustar toda vez com `set_time.py`). Requer o
DS18B20 (1-Wire) já ligado conforme `config.py` / `SPECS.md` seção 2.2
(DATA=4 com pull-up 4.7kΩ).

1. Suba os arquivos: `config.py`, `lcd_hd44780.py`, `ds18b20_sensor.py`,
   `set_time.py`, `test_normal_mode.py`.
2. Abra `set_time.py`, edite a data/hora atual no topo do arquivo e rode
   com **F5** (precisa repetir isso toda vez que a placa perder energia).
3. Abra `test_normal_mode.py` e rode com **F5**.
4. Esperado no display, atualizando a cada segundo:
   ```
   Sex, 17/07/2026
   14:30:05
   Temp: 24.5 C
   Relogio ESP32 BLE
   ```

## Rodar sozinho, sem Thonny (etapa 2 — modo autônomo)

MicroPython executa automaticamente um arquivo chamado **`main.py`**
sempre que o ESP32 recebe energia — não precisa estar conectado ao
Thonny nem ao computador, só ligado na tomada/carregador/power bank USB.

1. Edite a data/hora no topo de `main.py` (mesma lógica do `set_time.py`,
   já embutida aqui).
2. Suba `config.py`, `lcd_hd44780.py`, `ds18b20_sensor.py` e `main.py`
   pro ESP32 (nomes exatos, principalmente `main.py`).
3. Desconecte do Thonny e plugue o ESP32 em qualquer fonte USB — o
   display deve acender e mostrar o relógio sozinho.

**Limitação atual**: como não há RTC com bateria, a hora gravada em
`main.py` só fica correta a partir do momento em que você fez o upload.
Se a placa perder energia depois, ao religar ela volta pra essa mesma
hora gravada (desatualizada) até você editar e reenviar `main.py` de
novo. Isso será resolvido quando o app Android puder reenviar a hora
via BLE (etapa 4 do roadmap).

## Pinagem usada (ver `config.py` / `SPECS.md` seção 2.2)

| Sinal | GPIO |
|---|---|
| LCD RS | 13 |
| LCD E | 14 |
| LCD D4-D7 | 27, 26, 25, 33 |
| DS18B20 DATA | 4 |
