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

## Como testar o BLE (etapa 3 do roadmap)

1. Suba `config.py`, `lcd_hd44780.py`, `ds18b20_sensor.py`, `ble_service.py`,
   `storage.py` e `test_ble.py`.
2. Rode `test_ble.py` (F5). O display deve continuar mostrando o Modo
   Normal, e o ESP32 passa a anunciar via BLE como **"Relogio-ESP32"**.
3. No celular, abra um app BLE genérico (ex: **nRF Connect**), conecte no
   "Relogio-ESP32" e localize o serviço `8da7ea58-...`.
4. Teste cada característica (UUIDs completos no `SPECS.md` seção 4.2):
   - **SetDateTime** (write): envie o JSON `{"epoch": 1752500000}` (troque
     pelo epoch Unix atual) — o Shell do Thonny deve mostrar
     `SetDateTime recebido, RTC ajustado: (...)` e a hora no display muda.
   - **Marquee** (write): envie `{"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}`
     — o display muda pro Modo Letreiro na hora: o texto rola nas 4 linhas
     por `duration_s` segundos, depois volta sozinho pro Modo Normal.
   - **Config** (read/write): leia o valor atual (`{"temp_unit": "C"}`) ou
     escreva um novo.
   - **Status** (read/notify): ative notificações — a cada ~5s deve chegar
     um JSON com `temp_c` atualizado.

**Sem o sensor DS18B20 conectado?** Use `test_ble_sem_sensor.py` no lugar de
`test_ble.py` (suba `config.py`, `lcd_hd44780.py`, `ble_service.py`,
`storage.py` e `test_ble_sem_sensor.py` — não precisa do `ds18b20_sensor.py`).
Funciona igual, só sem leitura de temperatura (linha 3 do display mostra um
aviso, e o Status não inclui `temp_c`). É temporário — a versão completa
(`test_ble.py`) continua sendo a "oficial" do projeto.

## Como testar a persistência de configurações (etapa 6 do roadmap)

A unidade de temperatura (`temp_unit`, `"C"` ou `"F"`) agora é salva na
memória não-volátil (NVS) do ESP32 via o novo arquivo `storage.py` — ao
contrário da hora (RTC interno), essa configuração **sobrevive** a
reinícios e quedas de energia.

1. Suba `storage.py` junto com os demais arquivos do BLE (ver seção
   acima) e rode `test_ble.py` (ou `test_ble_sem_sensor.py`).
2. Pelo app Android (ou nRF Connect), escreva na característica **Config**:
   `{"temp_unit": "F"}`. O Shell do Thonny mostra `Config recebido: {...}`
   e, se tiver o sensor, a linha 3 do display passa a mostrar a
   temperatura em Fahrenheit.
3. Pressione o botão **EN/RESET** físico do ESP32 (ou desligue e ligue a
   alimentação) para simular uma queda de energia.
4. Depois do reboot, rode `test_ble.py` de novo: a temperatura já deve
   aparecer em Fahrenheit **sem precisar reconfigurar** — prova de que a
   escolha foi lida do NVS, e não perdida no reinício.
5. Para conferir pelo app: use o botão de **ler Config** — a resposta deve
   vir com `{"temp_unit": "F"}` mesmo logo após o boot, antes de qualquer
   nova escrita.

> A hora continua **não** sendo persistida (por design — ver SPECS.md
> seção 2.3/3.3): após o reset, é preciso reenviar a hora atual pelo app
> (botão de sincronizar hora) antes do Modo Normal voltar a mostrar a
> hora certa.

## Pinagem usada (ver `config.py` / `SPECS.md` seção 2.2)

| Sinal | GPIO |
|---|---|
| LCD RS | 13 |
| LCD E | 14 |
| LCD D4-D7 | 27, 26, 25, 33 |
| DS18B20 DATA | 4 |
