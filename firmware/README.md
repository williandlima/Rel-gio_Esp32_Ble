# Firmware — Relogio_Esp32_Ble (MicroPython)

## Instalação em um passo só (recomendado)

Depois que o hardware já está validado (etapas 1 e 2 abaixo), não precisa
mais abrir o Thonny e arrastar arquivo por arquivo toda vez que algo
mudar no firmware — `firmware/tools/` tem um empacotador e um instalador
que fazem isso com um comando só, no seu computador (não no ESP32).

Requisito único (uma vez só): `pip install mpremote`.

1. Feche o Thonny (ou qualquer outro programa com a porta serial aberta —
   só um programa por vez consegue falar com o ESP32).
2. Se não souber o nome da porta:
   ```bash
   python3 firmware/tools/install.py --list
   ```
3. Instale (troque `COM5` pela porta do seu ESP32 — no Windows costuma
   ser `COM` + um número; no Mac/Linux, algo como `/dev/tty.usbserial-...`
   ou `/dev/ttyUSB0`). Sem informar a porta, o script tenta descobrir
   sozinho:
   ```bash
   python3 firmware/tools/install.py COM5
   ```
4. O script copia os 8 arquivos que compõem o relógio (`config.py`,
   `lcd_hd44780.py`, `ds18b20_sensor.py`, `bigfont.py`, `ble_service.py`,
   `storage.py`, `clock_app.py`, `main.py`) e reinicia o ESP32 sozinho —
   o relógio já sobe rodando, sem precisar apertar RESET nem abrir o
   Thonny.

Pra guardar uma versão específica como backup (ex: antes de testar uma
mudança arriscada), gere um pacote `.zip` com as versões de cada arquivo
registradas num `MANIFEST.txt`:
```bash
python3 firmware/tools/package.py
```
Isso cria `firmware/dist/relogio-esp32-firmware-<data>.zip` (a pasta
`dist/` não vai para o Git — é um artefato gerado, refaça quando quiser).

As seções abaixo continuam valendo para quem está testando um pedaço do
firmware de cada vez (display sozinho, RTC sozinho, etc.) direto no
Thonny, com F5 e o Shell interativo — útil pra depurar, não só pra
instalar a versão final.

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

## Rodar sozinho, sem Thonny (modo autônomo)

MicroPython executa automaticamente um arquivo chamado **`main.py`**
sempre que o ESP32 recebe energia — não precisa estar conectado ao
Thonny nem ao computador, só ligado na tomada/carregador/power bank USB.

1. Suba os arquivos da aplicação (lista na seção abaixo), incluindo
   `main.py` com esse nome exato.
2. Desconecte do Thonny e plugue o ESP32 em qualquer fonte USB — o
   display acende e mostra o relógio sozinho, já anunciando por BLE.

`main.py` roda **a mesma aplicação completa** do `test_ble.py` (relógio +
temperatura + BLE + letreiro). Não há mais data/hora chumbada no arquivo:
como o RTC interno não tem bateria, ao ligar o relógio começa em
2000-01-01 e espera o app Android mandar a hora certa pelo botão
"Sincronizar hora". Já a unidade de temperatura (°C/°F) é lida da NVS e
**sobrevive** ao desligamento.

## Como testar o BLE (etapa 3 do roadmap)

1. Suba `config.py`, `lcd_hd44780.py`, `ble_service.py`, `storage.py`,
   `clock_app.py` e `test_ble.py` — mais `ds18b20_sensor.py`, se você
   tiver o sensor de temperatura ligado.
2. Rode `test_ble.py` (F5). O display deve continuar mostrando o Modo
   Normal, e o ESP32 passa a anunciar via BLE como **"Relogio-ESP32"**.
3. No celular, abra um app BLE genérico (ex: **nRF Connect**), conecte no
   "Relogio-ESP32" e localize o serviço `8da7ea58-...`.
4. Teste cada característica (UUIDs completos no `SPECS.md` seção 4.2):
   - **SetDateTime** (write): envie o JSON `{"epoch": 1752500000}` (troque
     pelo epoch Unix atual) — o Shell do Thonny deve mostrar
     `SetDateTime recebido, RTC ajustado: (...)` e a hora no display muda.
   - **Marquee** (write): envie `{"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}`
     — o display muda pro Modo Letreiro na hora: o texto rola nas 4 linhas,
     entrando pela direita e saindo pela esquerda, por `duration_s`
     segundos, depois volta sozinho pro Modo Normal. Para cancelar antes
     do tempo acabar, envie `{"text": ""}` ou `{"duration_s": 0}`.
     Existem mais dois modos, ligados pelo campo `"mode"` — `"lines"`
     (4 campos, um por linha, cada um rolando por conta própria) e
     `"big"` (texto ampliado em blocos, ocupando as 4 linhas). Detalhes
     e exemplos de payload no `SPECS.md`, seção 4.2.
   - **Config** (read/write): leia o valor atual (`{"temp_unit": "C"}`) ou
     escreva um novo.
   - **Status** (read/notify): ative notificações — a cada ~5s deve chegar
     um JSON com `temp_c` atualizado. A **leitura** de Status também
     devolve o JSON inteiro (antes vinha cortado em 20 bytes, porque o
     buffer padrão de cada característica no MicroPython é desse tamanho —
     hoje `ble_service.py` chama `gatts_set_buffer` para 512 bytes).

**Sem o sensor DS18B20 conectado?** Não precisa fazer nada de diferente: o
firmware detecta a ausência do sensor sozinho, sobe normalmente e mostra
"Sem sensor de temp." na linha 3 (o Status simplesmente não inclui
`temp_c`). O arquivo `test_ble_sem_sensor.py` continua existindo só por
compatibilidade com o passo a passo antigo — hoje ele é idêntico ao
`test_ble.py`.

## Organização dos arquivos

| Arquivo | Papel |
|---|---|
| `config.py` | Pinagem (ver SPECS.md seção 2.2) |
| `lcd_hd44780.py` | Driver do display, 4 bits, com cache de linha |
| `ds18b20_sensor.py` | Sensor de temperatura (leitura em duas etapas, sem bloquear) |
| `bigfont.py` | Fonte de blocos do Modo Letreiro Ampliado |
| `ble_service.py` | Serviço GATT; o IRQ só enfileira, `tick()` processa |
| `storage.py` | Configurações na NVS |
| `clock_app.py` | **A aplicação**: Modo Normal + Modo Letreiro + BLE |
| `main.py` | Autoboot — só chama `clock_app.run()` |
| `test_ble.py` | Igual ao `main.py`, para rodar com F5 no Thonny |
| `test_ble_sem_sensor.py` | Compatibilidade; idêntico ao `test_ble.py` |
| `set_time.py`, `test_display.py`, `test_normal_mode.py` | Testes isolados das etapas 1 e 2 |
| `tools/install.py`, `tools/package.py` | Rodam no **computador**, não no ESP32 — instalação/empacotamento em um passo (ver seção acima) |

## Como testar a persistência de configurações (etapa 6 do roadmap)

A unidade de temperatura (`temp_unit`, `"C"` ou `"F"`) agora é salva na
memória não-volátil (NVS) do ESP32 via o novo arquivo `storage.py` — ao
contrário da hora (RTC interno), essa configuração **sobrevive** a
reinícios e quedas de energia.

1. Suba `storage.py` junto com os demais arquivos da aplicação (ver seção
   acima) e rode `test_ble.py`.
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
