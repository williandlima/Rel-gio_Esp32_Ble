# App Android — Relogio_Esp32_Ble

App Kotlin simples (sem bibliotecas externas — só APIs nativas de Bluetooth
Low Energy do Android) para configurar o relógio via BLE, seguindo o
protocolo definido no `SPECS.md` (seção 4) e implementado em
`firmware/ble_service.py`.

## Como criar o projeto no Android Studio

1. Abra o Android Studio → **New Project** → template **"Empty Views Activity"**
   (não "Empty Activity" com Compose — este app usa XML/ViewBinding).
2. Configure:
   - **Name**: RelogioESP32
   - **Package name**: `com.relogioesp32.ble` (importante — precisa bater
     com o pacote usado nos arquivos deste repositório)
   - **Language**: Kotlin
   - **Minimum SDK**: API 26 (Android 8.0) ou superior
3. Deixe o Android Studio criar o projeto e sincronizar o Gradle.

## Como aplicar os arquivos deste repositório

1. No `app/build.gradle.kts` gerado, dentro do bloco `android { ... }`,
   adicione (se ainda não existir):
   ```kotlin
   buildFeatures {
       viewBinding = true
   }
   ```
2. Copie os arquivos deste repositório por cima dos gerados pelo Android
   Studio (mesmos caminhos):
   - `app/src/main/AndroidManifest.xml`
   - `app/src/main/java/com/relogioesp32/ble/MainActivity.kt`
   - `app/src/main/java/com/relogioesp32/ble/BleManager.kt`
   - `app/src/main/res/layout/activity_main.xml`
3. Sincronize o Gradle de novo (Android Studio deve pedir automaticamente).

## Como testar

Pré-requisito: o ESP32 rodando `test_ble.py` (ou uma versão futura do
firmware com BLE ativo), anunciando como **"Relogio-ESP32"**.

1. Rode o app num celular Android físico (BLE não funciona bem em
   emulador) conectado via cabo USB, com depuração USB ativada.
2. Toque em **"Conectar ao Relogio-ESP32"** — conceda as permissões de
   Bluetooth/Localização pedidas.
3. Quando conectar, o texto de status muda para "Conectado" e o app
   assina as notificações de **Status** automaticamente (deve começar a
   aparecer `{"mode": "normal", "temp_c": ..., "connected": true}` a cada
   ~5s).
4. Toque em **"Sincronizar hora com o celular"** — a hora do display do
   relógio deve mudar para a hora atual (já ajustada pro fuso horário
   local do celular, ao contrário do teste manual anterior via nRF Connect
   que usava UTC puro).
5. Preencha o texto/duração/velocidade do letreiro e toque em **"Enviar
   letreiro"** — por enquanto só aparece no Shell do Thonny (`Marquee
   recebido: {...}`), o comportamento real no display é a etapa 5 do
   roadmap.
6. Teste **"Salvar configuracao"** (Celsius/Fahrenheit) e **"Ler
   configuracao atual"**.

## Estrutura

```
app/src/main/
  AndroidManifest.xml
  java/com/relogioesp32/ble/
    MainActivity.kt      Tela única, permissões e callbacks de UI
    BleManager.kt         Cliente BLE (scan, connect, GATT read/write/notify)
  res/layout/
    activity_main.xml     Layout da tela única
```
