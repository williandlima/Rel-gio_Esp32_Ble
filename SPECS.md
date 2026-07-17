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
| RTC | DS3231 (módulo) | I2C | Bateria coin-cell própria (CR2032), mantém hora sem USB |
| Sensor de temperatura | DS18B20 | 1-Wire | Isolado do calor do ESP32 por fio, ambiente real |
| Alimentação | USB 5V (micro-USB ou USB-C, conforme a placa) | — | Sem bateria de backup do sistema (só o RTC tem a própria) |
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
| I2C SDA (RTC) | GPIO21 | |
| I2C SCL (RTC) | GPIO22 | |
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
- Sem bateria de backup para o sistema — se faltar USB, o relógio desliga,
  mas o **RTC DS3231 mantém a hora certa** (bateria própria) para quando a
  energia voltar.

## 3. Firmware

### 3.0 Linguagem e Ambiente de Desenvolvimento

- **Linguagem/Framework**: MicroPython (porta oficial para ESP32).
- **IDE/Ferramenta**: Thonny (upload de arquivos, REPL interativo para testes
  de sensores/display isolados antes de integrar tudo).
- **BLE**: módulo `bluetooth` (ubluetooth) nativo do MicroPython — API de
  baixo nível baseada em IRQ/callbacks; o serviço GATT customizado (seção 4)
  será implementado manualmente sobre essa API.
- **Drivers**: sem bibliotecas prontas equivalentes ao Arduino — os drivers
  de LCD paralelo (4 bits), DS3231 (I2C) e DS18B20 (`onewire`/`ds18x20`,
  estes já inclusos no firmware MicroPython) serão escritos/adaptados
  especificamente para este projeto.

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

- **Hora/data**: mantidas pelo RTC DS3231 (bateria própria), lidas pelo
  ESP32 a cada ciclo.
- **Configurações** (ex: unidade de temperatura °C/°F, brilho/contraste se
  controlável por software): salvas em NVS via `esp32.NVS()` (MicroPython),
  sobrevivem a reinícios.
- **Letreiro**: não persiste entre reinícios (efêmero) — se o ESP32
  reiniciar durante o letreiro, volta ao Modo Normal.

## 4. Comunicação BLE

### 4.1 Padrão

GATT customizado, payloads em **JSON** (texto legível, fácil de debugar
inclusive com apps BLE genéricos como nRF Connect).

### 4.2 Serviço e Características (proposta inicial)

| Característica | UUID (a gerar) | Propriedade | Payload (JSON) |
|---|---|---|---|
| SetDateTime | custom | Write | `{"epoch": 1752500000}` |
| Marquee | custom | Write | `{"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}` |
| Config | custom | Read/Write | `{"temp_unit": "C"}` |
| Status | custom | Read/Notify | `{"mode": "normal", "temp_c": 24.5, "connected": true}` |

> UUIDs definitivos serão gerados na etapa de implementação do firmware.

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
- Bateria de backup do sistema (só o RTC tem bateria própria).
- Fila de múltiplas mensagens de letreiro (apenas uma mensagem ativa por vez).
- Alarmes, timers ou outras funcionalidades além de relógio/temperatura/letreiro.

## 7. Ordem de Desenvolvimento (Roadmap)

Trabalho incremental, com verificação/aprovação de cada etapa antes de avançar
para a próxima:

1. **Display** — driver LCD paralelo 4 bits (HD44780) em MicroPython, teste
   de escrita nas 4 linhas.
2. **RTC + Temperatura** — integra DS3231 (I2C) e DS18B20 (1-Wire), fecha o
   Modo Normal completo (data + hora + temperatura no display).
3. **Esqueleto BLE** — serviço GATT mínimo funcionando (características
   SetDateTime/Marquee/Config/Status), testável com app BLE genérico
   (ex: nRF Connect) antes do app dedicado existir.
4. **App Android** — desenvolvido contra o BLE já funcional do firmware.
5. **Modo Letreiro** — scroll + duração, acionado pelas mensagens recebidas
   via BLE (firmware + app).
6. **Persistência** (NVS) e revisão final de todas as configurações.
