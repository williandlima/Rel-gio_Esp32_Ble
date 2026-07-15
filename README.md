# Relogio_Esp32_Ble

Relógio de mesa baseado em ESP32 que exibe data, hora e temperatura ambiente
em um display de caracteres 20x4, com um modo de letreiro configurável via
Bluetooth Low Energy (BLE) a partir de um app Android dedicado.

Especificação completa (hardware, firmware, protocolo BLE, roadmap): [`SPECS.md`](./SPECS.md).

## Stack

- **Microcontrolador**: ESP32
- **Firmware**: MicroPython, desenvolvido/gravado via [Thonny](https://thonny.org)
- **Display**: NHD-0420E2Z-NSW-BBW (20x4, paralelo HD44780, modo 4 bits)
- **RTC**: DS3231 (I2C)
- **Temperatura**: DS18B20 (1-Wire)
- **App**: Android (Kotlin), configuração via BLE

## Status

Seguindo o roadmap incremental definido no `SPECS.md` (seção 7):

- [~] 1. Display — driver LCD 4-bit + script de teste prontos (`firmware/`), aguardando validação em bancada
- [ ] 2. RTC + Temperatura (Modo Normal completo)
- [ ] 3. Esqueleto do serviço BLE
- [ ] 4. App Android
- [ ] 5. Modo Letreiro
- [ ] 6. Persistência (NVS) e revisão final

## Estrutura

```
SPECS.md          Especificação completa do projeto
firmware/          Firmware ESP32 em MicroPython (ver firmware/README.md para instruções de uso via Thonny)
android-app/       App Android (ainda não iniciado)
```
