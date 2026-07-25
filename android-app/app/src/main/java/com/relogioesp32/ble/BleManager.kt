package com.relogioesp32.ble

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer
import java.util.UUID

// Cliente BLE do serviço GATT definido em firmware/ble_service.py (ver
// SPECS.md seção 4.2). Usa a API nativa do Android (sem bibliotecas
// externas) para minimizar dependências.
//
// Duas regras que o Android impõe e que este arquivo respeita:
//
// 1. Só pode existir UMA operação GATT em voo por vez (write, read ou
//    escrita de descritor). Disparar a segunda antes do callback da
//    primeira faz a segunda ser silenciosamente descartada. Por isso tudo
//    passa por uma fila (opQueue) que só avança no callback.
// 2. Todo BluetoothGatt precisa de close(). Sem isso cada ciclo
//    conectar/desconectar vaza um registro de cliente GATT, e depois de
//    algumas dezenas de ciclos o app simplesmente para de conectar.
//
// Nota: usa a API "clássica" (característica.value + callbacks sem o
// parâmetro value), marcada como deprecated a partir da API 33, mas ainda
// funcional e com suporte a uma faixa bem maior de versões do Android sem
// precisar de checagens condicionais por SDK.
class BleManager(private val context: Context) {

    companion object {
        private const val TAG = "BleManager"
        const val DEVICE_NAME = "Relogio-ESP32"

        val SERVICE_UUID: UUID = UUID.fromString("8da7ea58-d7a9-4740-899d-e790d280bbec")
        val CHAR_SET_DATETIME: UUID = UUID.fromString("05dbf463-f5f4-4b26-9432-a063782076d3")
        val CHAR_MARQUEE: UUID = UUID.fromString("361e7fd4-683a-49bc-a3ad-9d0e284db3c7")
        val CHAR_CONFIG: UUID = UUID.fromString("592e0d32-9975-435b-8986-1ab319153779")
        val CHAR_STATUS: UUID = UUID.fromString("8f86a231-9483-468f-b065-2082f2cadc88")
        private val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        // O firmware remonta escritas fragmentadas (ver ble_service.py), e
        // 20 bytes cabe até no MTU mínimo do BLE (23).
        private const val CHUNK_SIZE = 20
        private const val SCAN_TIMEOUT_MS = 15_000L
    }

    var onLog: ((String) -> Unit)? = null
    var onConnectionStateChange: ((connected: Boolean) -> Unit)? = null
    var onReady: (() -> Unit)? = null
    var onScanTimeout: (() -> Unit)? = null
    var onStatusChanged: ((json: String) -> Unit)? = null
    var onConfigRead: ((json: String) -> Unit)? = null

    private val bluetoothManager =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val adapter: BluetoothAdapter? = bluetoothManager.adapter
    private val handler = Handler(Looper.getMainLooper())

    private var gatt: BluetoothGatt? = null
    private var scanning = false

    fun isBluetoothEnabled(): Boolean = adapter?.isEnabled == true

    // ---- Descoberta ----

    private val scanTimeoutRunnable = Runnable {
        if (scanning) {
            stopScan()
            log("$DEVICE_NAME nao encontrado. Ele esta ligado e por perto?")
            onScanTimeout?.invoke()
        }
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val device = result.device ?: return
            log("Encontrado $DEVICE_NAME, conectando...")
            stopScan()
            connectToDevice(device)
        }

        override fun onScanFailed(errorCode: Int) {
            scanning = false
            handler.removeCallbacks(scanTimeoutRunnable)
            log("Falha ao escanear (codigo $errorCode)")
            onScanTimeout?.invoke()
        }
    }

    @Suppress("MissingPermission")
    fun startScan() {
        val scanner = adapter?.bluetoothLeScanner
        if (adapter == null || !adapter.isEnabled || scanner == null) {
            log("Bluetooth nao disponivel ou desligado")
            onScanTimeout?.invoke()
            return
        }
        if (scanning) return
        scanning = true
        log("Procurando $DEVICE_NAME...")

        // Filtro por nome no proprio radio: mais eficiente do que receber
        // todo dispositivo BLE das redondezas e descartar em software.
        // (O anuncio do ESP32 nao cabe o UUID de 128 bits junto do nome
        // dentro dos 31 bytes do pacote, por isso filtramos pelo nome.)
        val filters = listOf(ScanFilter.Builder().setDeviceName(DEVICE_NAME).build())
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        scanner.startScan(filters, settings, scanCallback)
        handler.postDelayed(scanTimeoutRunnable, SCAN_TIMEOUT_MS)
    }

    @Suppress("MissingPermission")
    fun stopScan() {
        handler.removeCallbacks(scanTimeoutRunnable)
        if (!scanning) return
        scanning = false
        try {
            adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        } catch (e: Exception) {
            Log.w(TAG, "stopScan falhou", e)
        }
    }

    @Suppress("MissingPermission")
    private fun connectToDevice(device: BluetoothDevice) {
        closeGatt()  // garante que nao sobrou nenhum cliente GATT aberto
        gatt = device.connectGatt(context, false, gattCallback)
    }

    // ---- Ciclo de vida ----

    @Suppress("MissingPermission")
    fun disconnect() {
        stopScan()
        // close() acontece em onConnectionStateChange(STATE_DISCONNECTED).
        gatt?.disconnect()
    }

    /** Libera tudo. Chamar quando a tela for destruída de vez. */
    fun release() {
        stopScan()
        @Suppress("MissingPermission")
        gatt?.disconnect()
        closeGatt()
    }

    @Suppress("MissingPermission")
    private fun closeGatt() {
        val g = gatt ?: return
        gatt = null
        opQueue.clear()
        currentOp = null
        chunkQueue.clear()
        chunkCharacteristic = null
        try {
            g.close()
        } catch (e: Exception) {
            Log.w(TAG, "close falhou", e)
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {
        @Suppress("MissingPermission")
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    log("Conectado, solicitando MTU maior...")
                    onConnectionStateChange?.invoke(true)
                    // MTU padrao (23 bytes) limita o tamanho das
                    // notificacoes de Status. O ESP32 aceita ate 256.
                    g.requestMtu(247)
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    log("Desconectado")
                    closeGatt()
                    onConnectionStateChange?.invoke(false)
                }
            }
        }

        @Suppress("MissingPermission")
        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            log("MTU negociado: $mtu bytes, descobrindo servicos...")
            g.discoverServices()
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                log("Falha ao descobrir servicos: $status")
                return
            }
            log("Servicos descobertos.")
            // A partir daqui as caracteristicas existem: so agora faz
            // sentido liberar os botoes da tela.
            enqueue(Op.EnableNotify(CHAR_STATUS))
            enqueue(Op.Read(CHAR_CONFIG))
            onReady?.invoke()
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicRead(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS && characteristic.uuid == CHAR_CONFIG) {
                onConfigRead?.invoke(String(characteristic.value ?: ByteArray(0)))
            }
            finishOp()
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            // Notificacao: nao faz parte da fila, chega quando o ESP32 quiser.
            if (characteristic.uuid == CHAR_STATUS) {
                onStatusChanged?.invoke(String(characteristic.value ?: ByteArray(0)))
            }
        }

        override fun onCharacteristicWrite(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                log("Escrita em ${characteristic.uuid} falhou ($status)")
                finishOp()
                return
            }
            if (chunkQueue.isNotEmpty()) {
                if (!sendNextChunk()) finishOp()
            } else {
                log("Escrita em ${characteristic.uuid}: OK")
                finishOp()
            }
        }

        override fun onDescriptorWrite(
            g: BluetoothGatt,
            descriptor: BluetoothGattDescriptor,
            status: Int
        ) {
            log("Notificacoes de Status ativadas.")
            finishOp()
        }
    }

    // ---- Fila de operações GATT ----

    private sealed class Op(val uuid: UUID) {
        class Write(uuid: UUID, val payload: ByteArray) : Op(uuid)
        class Read(uuid: UUID) : Op(uuid)
        class EnableNotify(uuid: UUID) : Op(uuid)
    }

    private val opQueue = ArrayDeque<Op>()
    private var currentOp: Op? = null
    private val chunkQueue = ArrayDeque<ByteArray>()
    private var chunkCharacteristic: BluetoothGattCharacteristic? = null

    private fun enqueue(op: Op) {
        opQueue.addLast(op)
        if (currentOp == null) startNextOp()
    }

    private fun finishOp() {
        currentOp = null
        chunkCharacteristic = null
        chunkQueue.clear()
        startNextOp()
    }

    @Suppress("DEPRECATION", "MissingPermission")
    private fun startNextOp() {
        val g = gatt
        if (g == null) {
            opQueue.clear()
            currentOp = null
            return
        }
        val op = opQueue.removeFirstOrNull() ?: return
        currentOp = op

        val char = findCharacteristic(op.uuid)
        if (char == null) {
            log("Caracteristica nao encontrada: ${op.uuid}")
            finishOp()
            return
        }

        val started = when (op) {
            is Op.Write -> {
                // A API classica NAO fragmenta sozinha payloads maiores que
                // o MTU: manda uma vez, truncado, e nao reenvia o resto. Por
                // isso fatiamos aqui e o firmware remonta do outro lado.
                chunkQueue.clear()
                op.payload.toList().chunked(CHUNK_SIZE).forEach {
                    chunkQueue.addLast(it.toByteArray())
                }
                chunkCharacteristic = char
                sendNextChunk()
            }
            is Op.Read -> g.readCharacteristic(char)
            is Op.EnableNotify -> {
                g.setCharacteristicNotification(char, true)
                val descriptor = char.getDescriptor(CCCD_UUID)
                if (descriptor == null) {
                    false
                } else {
                    descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                    g.writeDescriptor(descriptor)
                }
            }
        }

        if (!started) {
            log("Nao foi possivel iniciar a operacao GATT")
            finishOp()
        }
    }

    @Suppress("DEPRECATION", "MissingPermission")
    private fun sendNextChunk(): Boolean {
        val g = gatt ?: return false
        val char = chunkCharacteristic ?: return false
        val chunk = chunkQueue.removeFirstOrNull() ?: return false
        char.value = chunk
        return g.writeCharacteristic(char)
    }

    private fun findCharacteristic(uuid: UUID): BluetoothGattCharacteristic? {
        return gatt?.getService(SERVICE_UUID)?.getCharacteristic(uuid)
    }

    // ---- API da tela ----

    fun writeSetDateTime(epochSeconds: Long) {
        val json = JSONObject().put("epoch", epochSeconds).toString()
        write(CHAR_SET_DATETIME, json)
    }

    /** Modo Rolagem: um texto só, rolando nas 4 linhas. */
    fun writeMarqueeScroll(text: String, durationS: Int, speedMs: Int) {
        val json = JSONObject()
            .put("mode", "scroll")
            .put("text", toDisplayableAscii(text))
            .put("duration_s", durationS)
            .put("speed_ms", speedMs)
            .toString()
        write(CHAR_MARQUEE, json)
    }

    /** Modo 4 linhas: cada campo rola de forma independente na sua linha. */
    fun writeMarqueeLines(lines: List<String>, durationS: Int, speedMs: Int) {
        val array = JSONArray()
        lines.forEach { array.put(toDisplayableAscii(it)) }
        val json = JSONObject()
            .put("mode", "lines")
            .put("lines", array)
            .put("duration_s", durationS)
            .put("speed_ms", speedMs)
            .toString()
        write(CHAR_MARQUEE, json)
    }

    /** Modo Ampliado: um caractere por vez ocupando as 4 linhas. */
    fun writeMarqueeBig(text: String, durationS: Int, speedMs: Int) {
        val json = JSONObject()
            .put("mode", "big")
            .put("text", toDisplayableAscii(text))
            .put("duration_s", durationS)
            .put("speed_ms", speedMs)
            .toString()
        write(CHAR_MARQUEE, json)
    }

    /** Interrompe o letreiro e volta ao Modo Normal (duração zero). */
    fun writeMarqueeStop() {
        write(CHAR_MARQUEE, JSONObject().put("duration_s", 0).toString())
    }

    fun writeConfig(tempUnit: String) {
        val json = JSONObject().put("temp_unit", tempUnit).toString()
        write(CHAR_CONFIG, json)
    }

    fun readConfig() {
        if (gatt == null) {
            log("Nao conectado")
            return
        }
        enqueue(Op.Read(CHAR_CONFIG))
    }

    private fun write(uuid: UUID, json: String) {
        if (gatt == null) {
            log("Nao conectado")
            return
        }
        enqueue(Op.Write(uuid, json.toByteArray(Charsets.UTF_8)))
    }

    /**
     * O display do relógio é um HD44780: ele não tem acentos nem cedilha no
     * gerador de caracteres, e mostraria símbolos aleatórios no lugar. Aqui
     * "ação" vira "acao" antes de ir para o ar — o que o usuário digitou
     * continua legível, só sem os acentos.
     */
    private fun toDisplayableAscii(text: String): String {
        val semAcento = Normalizer.normalize(text, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
        return buildString {
            for (ch in semAcento) {
                append(if (ch.code in 0x20..0x7D) ch else '?')
            }
        }
    }

    private fun log(msg: String) {
        Log.d(TAG, msg)
        onLog?.invoke(msg)
    }
}
