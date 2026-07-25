# Relogio_Esp32_Ble — Especificação do Projeto

## 1. Visão Geral

Relógio de mesa baseado em ESP32 que exibe **data, hora e temperatura ambiente**
simultaneamente em um display de caracteres 20x4, com um modo adicional de
**letreiro** (marquee) configurável via Bluetooth Low Energy (BLE) a partir de
um app Android dedicado.

## 2. Hardware

### 2.1 Lista de Componentes (BOM)

| Componente | Modelo | Interface | Observação |
|---|---|---|---|
| Microcontrolador | ESP32 DevKit (30/38 pinos) | — | Wi-Fi não utilizado, apenas BLE |
| Display | NHD-0420E2Z-NSW-BBW | Paralelo HD44780, modo 4 bits | 20 colunas x 4 linhas, fundo azul/texto branco |
| RTC | Interno do ESP32 (`machine.RTC`) | — | Sem bateria de backup — perde a hora ao desligar/resetar (ver seção 2.3) |
| Sensor de temperatura | DS18B20 | 1-Wire | Isolado do calor do ESP32 por fio, ambiente real |
| Alimentação | USB 5V (micro-USB ou USB-C, conforme a placa) | — | Sem bateria de backup no sistema |
| Resistor pull-up 1-Wire | 4.7kΩ | — | Entre dado do DS18B20 e 3.3V |
| Potenciômetro contraste LCD | 10kΩ | — | Pino Vo do display |

### 2.2 Pinagem Proposta (ESP32 DevKit, 3.3V)

| Sinal | GPIO | Observação |
|---|---|---|
| LCD RS | GPIO13 | |
| LCD E | GPIO14 | |
| LCD D4 | GPIO27 | |
| LCD D5 | GPIO26 | |
| LCD D6 | GPIO25 | |
| LCD D7 | GPIO33 | |
| LCD VDD | **5V** (pino VIN/5V do ESP32, vindo do USB) | Ver nota abaixo — este display **não opera em 3.3V** |
| LCD Vo | Potenciômetro 10k (entre GND e VDD 5V) | Ajuste de contraste |
| LCD RW | GND | Fixado em modo escrita (RW=0) |
| LCD Backlight (LED+) | 5V via resistor série (~100-220Ω) | Conforme datasheet |
| DS18B20 DATA | GPIO4 | Pull-up 4.7kΩ para 3.3V |

> Pinos de strapping do ESP32 (GPIO0, 2, 12, 15) evitados propositalmente.
> Pinagem final pode ser ajustada conforme a placa DevKit específica usada.

> **Importante — VDD do display**: o NHD-0420E2Z-NSW-BBW exige alimentação
> de **5V** no VDD (não suporta 3.3V). Use o pino 5V/VIN do ESP32 (disponível
> na maioria das DevKits, vindo direto do USB) para VDD e para o backlight.
> Os sinais de dados (RS, E, D4-D7) continuam saindo dos GPIOs em 3.3V
> normalmente — o HD44780 reconhece 3.3V como nível lógico alto mesmo com
> VDD em 5V, sem necessidade de conversor de nível.

### 2.3 Alimentação

- Fonte: USB 5V (do próprio conector da placa ESP32).
- Sem bateria de backup no sistema — se faltar USB, o relógio desliga e
  **perde a hora** (RTC interno do ESP32, sem bateria própria). Ao religar,
  a hora precisa ser reenviada via BLE (characteristic SetDateTime, seção 4.2)
  antes do Modo Normal voltar a mostrar hora correta.

## 3. Firmware

### 3.0 Linguagem e Ambiente de Desenvolvimento

- **Linguagem/Framework**: MicroPython (porta oficial para ESP32).
- **IDE/Ferramenta**: Thonny (upload de arquivos, REPL interativo para testes
  de sensores/display isolados antes de integrar tudo).
- **BLE**: módulo `bluetooth` (ubluetooth) nativo do MicroPython — API de
  baixo nível baseada em IRQ/callbacks; o serviço GATT customizado (seção 4)
  será implementado manualmente sobre essa API.
- **Drivers**: sem bibliotecas prontas equivalentes ao Arduino — o driver de
  LCD paralelo (4 bits) foi escrito especificamente para este projeto; o
  DS18B20 usa os módulos `onewire`/`ds18x20` já inclusos no firmware
  MicroPython; a hora usa `machine.RTC` (nativo, interno do ESP32).

### 3.1 Modo Normal (padrão, tudo simultâneo)

Layout fixo nas 4 linhas do display, sem alternância de telas:

```
Linha 1: Ter, 14/07/2026        <- dia da semana + data
Linha 2:      14:32:07          <- hora (HH:MM:SS)
Linha 3: Temp: 24.5 C           <- leitura do DS18B20
Linha 4: [status BLE / livre]   <- indicador de conexão BLE, ou em branco
```

### 3.2 Modo Letreiro

- Ativado quando o app envia uma mensagem via BLE.
- Ocupa as 4 linhas do display por completo com o texto rolando (scroll
  horizontal contínuo).
- Parâmetros configuráveis pelo app: **texto**, **duração total** (segundos)
  e **velocidade de rolagem** (ms por passo, com valor padrão sensato).
- Apenas **uma mensagem ativa** por vez — uma nova mensagem recebida
  substitui a anterior e reinicia a contagem de duração.
- Ao expirar a duração configurada, o firmware **volta automaticamente**
  para o Modo Normal.

### 3.3 Persistência

- **Hora/data**: mantidas pelo RTC interno do ESP32 (`machine.RTC`) enquanto
  a placa estiver ligada. **Não sobrevive a queda de energia/reset** — o
  app precisa reenviar a hora via BLE sempre que isso acontecer.
- **Configurações** (unidade de temperatura °C/°F): salvas em NVS via
  `esp32.NVS()` (MicroPython, módulo `storage.py`), sobrevivem a
  reinícios — implementado e validado na etapa 6.
- **Letreiro**: não persiste entre reinícios (efêmero) — se o ESP32
  reiniciar durante o letreiro, volta ao Modo Normal.

## 4. Comunicação BLE

### 4.1 Padrão

GATT customizado, payloads em **JSON** (texto legível, fácil de debugar
inclusive com apps BLE genéricos como nRF Connect).

Sem pareamento/bonding e sem autenticação nas características: qualquer
aparelho ao alcance consegue ajustar a hora, mandar letreiro ou trocar a
unidade de temperatura. É uma decisão consciente para um relógio de mesa
doméstico — se o projeto um dia sair desse contexto, é o primeiro ponto a
revisar.

**Limites do transporte** (aprendidos na prática, ver seção 8):

- O buffer de cada característica no MicroPython é de 20 bytes por padrão;
  o firmware chama `gatts_set_buffer(handle, 512)` para aceitar payloads
  inteiros e devolver leituras completas.
- A API clássica de escrita do Android não fragmenta payloads maiores que
  o MTU — trunca e não reenvia. O app fatia em pedaços de 20 bytes e o
  firmware remonta até formar um JSON válido (com timeout de 3 s para
  descartar fragmento órfão).

### 4.2 Serviço e Características

Serviço: `8da7ea58-d7a9-4740-899d-e790d280bbec`

| Característica | UUID | Propriedade | Payload (JSON) |
|---|---|---|---|
| SetDateTime | `05dbf463-f5f4-4b26-9432-a063782076d3` | Write | `{"epoch": 1752500000}` |
| Marquee | `361e7fd4-683a-49bc-a3ad-9d0e284db3c7` | Write | `{"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}` |
| Config | `592e0d32-9975-435b-8986-1ab319153779` | Read/Write | `{"temp_unit": "C"}` |
| Status | `8f86a231-9483-468f-b065-2082f2cadc88` | Read/Notify | `{"mode": "normal", "temp_c": 24.5, "connected": true}` |

> **Nota sobre `epoch` (SetDateTime)**: é o epoch Unix padrão (segundos
> desde 1970-01-01), o mesmo formato que `System.currentTimeMillis()/1000`
> no Android. O firmware converte internamente para a época usada pelo
> `machine.RTC` do ESP32 (2000-01-01). Valores anteriores a 2020 são
> recusados pelo firmware.

> **Cancelar o letreiro**: enviar `{"text": ""}` ou `{"duration_s": 0}` na
> característica Marquee volta imediatamente ao Modo Normal. A duração é
> limitada a 3600 s e a velocidade tem piso de 50 ms por passo.

> **Texto do letreiro**: o HD44780 não tem acentos no gerador de
> caracteres. O app remove os acentos antes de enviar ("ação" → "acao") e
> o firmware troca por `?` qualquer caractere fora da faixa imprimível,
> como rede de segurança para escritas feitas por apps BLE genéricos.

### 4.3 App Android

- App dedicado (Kotlin), com telas para:
  - Ajustar data/hora do relógio (ou sincronizar com o horário do celular).
  - Enviar texto do letreiro + duração + velocidade.
  - Ajustar configurações gerais (unidade de temperatura, etc.).
  - Visualizar status atual (conectado, temperatura, modo).

## 5. Estrutura do Repositório (proposta)

```
/firmware        Projeto ESP32 (MicroPython — arquivos .py, fluxo via Thonny)
/android-app      Projeto Android (Kotlin)
/docs             Diagramas de conexão, protocolo BLE detalhado
SPECS.md          Este documento
README.md         Visão geral do projeto
```

## 6. Fora de Escopo (nesta fase)

- Wi-Fi / sincronização NTP (uso exclusivo de BLE, conforme definido).
- RTC externo com bateria de backup (decisão revertida — ver seção 2.1;
  hora é perdida em queda de energia e precisa ser reenviada via BLE).
- Fila de múltiplas mensagens de letreiro (apenas uma mensagem ativa por vez).
- Alarmes, timers ou outras funcionalidades além de relógio/temperatura/letreiro.

## 7. Ordem de Desenvolvimento (Roadmap)

Trabalho incremental, com verificação/aprovação de cada etapa antes de avançar
para a próxima:

1. **Display** — driver LCD paralelo 4 bits (HD44780) em MicroPython, teste
   de escrita nas 4 linhas.
2. **RTC interno + Temperatura** — integra `machine.RTC` (interno do ESP32)
   e DS18B20 (1-Wire), fecha o Modo Normal completo (data + hora +
   temperatura no display).
3. **Esqueleto BLE** — serviço GATT mínimo funcionando (características
   SetDateTime/Marquee/Config/Status), testável com app BLE genérico
   (ex: nRF Connect) antes do app dedicado existir.
4. **App Android** — desenvolvido contra o BLE já funcional do firmware.
5. **Modo Letreiro** — scroll + duração, acionado pelas mensagens recebidas
   via BLE (firmware + app).
6. **Persistência** (NVS) e revisão final de todas as configurações —
   `storage.py` salva `temp_unit` em NVS, lido no boot e reaplicado sem
   precisar reconfigurar pelo app após reinícios.

## 8. Convenção de Versionamento

Adotada a partir do Modo Letreiro (etapa 5) funcionando de ponta a ponta,
após dificuldades práticas em confirmar qual versão de um arquivo estava
realmente rodando no ESP32/celular durante os testes:

- **Firmware (MicroPython)**: todo arquivo `.py` reutilizável (`config.py`,
  `lcd_hd44780.py`, `ds18b20_sensor.py`, `ble_service.py`, etc.) define uma
  constante `VERSION = "nome_do_arquivo vN"` no topo. Incremente o número
  ao editar o arquivo.
- **Scripts principais** (`test_ble.py`, `test_ble_sem_sensor.py`, etc.):
  imprimem a própria versão **e** a de todos os módulos que importam, logo
  no início da execução — assim dá pra conferir no Shell do Thonny, com um
  único print, se o ESP32 está mesmo com o código esperado antes de
  investigar qualquer outro problema.
- **App Android**: `versionCode`/`versionName` em `app/build.gradle.kts`,
  incrementados a cada mudança relevante; exibidos no log da tela ao
  conectar.
- **Último marco totalmente validado em bancada**: commit `ad77ab7` —
  firmware `clock_app v1` / `ble_service v5` / `ds18b20_sensor v2` /
  `lcd_hd44780 v2` / `storage v2` / `config v1`, app Android
  `1.5-robustez-ble` (versionCode 6). Roadmap inteiro (etapas 1 a 6)
  concluído, com a rodada de robustez da seção 9 aplicada.
- Marco anterior (antes da revisão de código): commit `3a645fc`.
- Persistência de configurações (`storage.py`, etapa 6): `test_ble.py`
  e `test_ble_sem_sensor.py` subiram para v4.
- Redesign da interface do app Android (paleta e componentes conforme
  mockup do Claude Design): `versionCode 3` / `versionName
  "1.2-ui-redesign"`.
- Ajustes finos de UI (tema sem ActionBar padrão conflitante, 3 estados
  visuais do botão conectar/desconectar, controles desabilitados até
  conectar, log com rolagem própria): `versionCode 4` / `versionName
  "1.3-ui-polish"`.
- Cabeçalho com ícone/título/subtítulo e badge de status (verde
  "Conectado" / cinza "Desconectado" / "Conectando..."), e resumo de
  configuração + "Ver JSON" lado a lado, conforme print de referência
  mais detalhado: `versionCode 5` / `versionName "1.4-header-status"`.
- Rodada de robustez após revisão de código (ver seção 9):
  `ble_service v5`, `ds18b20_sensor v2`, `lcd_hd44780 v2`, `storage v2`,
  `clock_app v1` (novo) no firmware; `versionCode 6` / `versionName
  "1.5-robustez-ble"` no app.

## 9. Revisão de Código — Correções Aplicadas

Revisão de fragilidades feita com o projeto já funcionando de ponta a
ponta. As correções abaixo mantêm o comportamento validado em bancada e
atacam o que quebraria em uso prolongado:

**Transporte BLE**

- `gatts_set_buffer(512)` em todas as características. O padrão de 20
  bytes do MicroPython era a causa raiz da truncagem histórica: era o
  ESP32, e não o Android, que cortava as escritas — e uma leitura de
  Status vinha pela metade.
- No app, `gatt.close()` em toda desconexão. Sem isso cada ciclo
  conectar/desconectar vazava um registro de cliente GATT até o Android
  parar de conectar em silêncio.
- Fila serializada de operações GATT no app: o Android só aceita uma
  operação em voo por vez.

**Tempo real / responsividade**

- O IRQ do BLE passou a apenas enfileirar bytes; parse, callbacks e
  gravação em flash (NVS) acontecem no laço principal. Gravar na flash de
  dentro do IRQ do NimBLE era risco concreto de travar a placa.
- Leitura do DS18B20 dividida em duas etapas: os 750 ms de conversão não
  bloqueiam mais o laço, que era o motivo de o relógio pular segundos.
- LCD com cache por linha: só o que mudou vai ao barramento.
- Laço com granularidade de 20 ms (era 1 s), então o BLE responde quase
  na hora sem custo perceptível de CPU.

**Tolerância a falha**

- `try/except` no laço principal: erro pontual não mata mais o firmware.
- Sensor ausente ou com erro de CRC não impede o boot, e é redetectado
  sozinho a cada 30 s.
- Buffer de remontagem com timeout, payload validado por tipo, epoch
  absurdo recusado, NVS indisponível tolerada.
- Scan do app com timeout de 15 s, em vez de varrer para sempre.
