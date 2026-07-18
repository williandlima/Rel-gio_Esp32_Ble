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
import android.bluetooth.le.ScanResult
import android.content.Context
import android.util.Log
import java.util.UUID

// Cliente BLE do serviço GATT definido em firmware/ble_service.py (ver
// SPECS.md seção 4.2). Usa a API nativa do Android (sem bibliotecas
// externas) para minimizar dependências.
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
    }

    var onLog: ((String) -> Unit)? = null
    var onConnectionStateChange: ((connected: Boolean) -> Unit)? = null
    var onStatusChanged: ((json: String) -> Unit)? = null
    var onConfigRead: ((json: String) -> Unit)? = null

    private val bluetoothManager =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val adapter: BluetoothAdapter? = bluetoothManager.adapter
    private var gatt: BluetoothGatt? = null
    private var scanning = false

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val device = result.device
            @Suppress("MissingPermission")
            if (device.name == DEVICE_NAME) {
                log("Encontrado $DEVICE_NAME, conectando...")
                stopScan()
                connectToDevice(device)
            }
        }

        override fun onScanFailed(errorCode: Int) {
            log("Falha ao escanear (codigo $errorCode)")
        }
    }

    @Suppress("MissingPermission")
    fun startScan() {
        val scanner = adapter?.bluetoothLeScanner
        if (adapter == null || adapter.isEnabled == false || scanner == null) {
            log("Bluetooth nao disponivel ou desligado")
            return
        }
        if (scanning) return
        scanning = true
        log("Procurando $DEVICE_NAME...")
        scanner.startScan(scanCallback)
    }

    @Suppress("MissingPermission")
    fun stopScan() {
        if (!scanning) return
        scanning = false
        adapter?.bluetoothLeScanner?.stopScan(scanCallback)
    }

    @Suppress("MissingPermission")
    private fun connectToDevice(device: BluetoothDevice) {
        gatt = device.connectGatt(context, false, gattCallback)
    }

    @Suppress("MissingPermission")
    fun disconnect() {
        gatt?.disconnect()
    }

    private val gattCallback = object : BluetoothGattCallback() {
        @Suppress("MissingPermission")
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    log("Conectado, descobrindo servicos...")
                    onConnectionStateChange?.invoke(true)
                    g.discoverServices()
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    log("Desconectado")
                    onConnectionStateChange?.invoke(false)
                    gatt = null
                }
            }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                log("Falha ao descobrir servicos: $status")
                return
            }
            log("Servicos descobertos.")
            enableStatusNotifications()
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
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            if (characteristic.uuid == CHAR_STATUS) {
                onStatusChanged?.invoke(String(characteristic.value ?: ByteArray(0)))
            }
        }

        override fun onCharacteristicWrite(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            val ok = status == BluetoothGatt.GATT_SUCCESS
            log("Escrita em ${characteristic.uuid}: ${if (ok) "OK" else "falhou ($status)"}")
        }
    }

    private fun findCharacteristic(uuid: UUID): BluetoothGattCharacteristic? {
        return gatt?.getService(SERVICE_UUID)?.getCharacteristic(uuid)
    }

    @Suppress("DEPRECATION", "MissingPermission")
    private fun writeCharacteristic(uuid: UUID, payload: ByteArray) {
        val g = gatt
        if (g == null) {
            log("Nao conectado")
            return
        }
        val char = findCharacteristic(uuid)
        if (char == null) {
            log("Caracteristica nao encontrada: $uuid")
            return
        }
        char.value = payload
        g.writeCharacteristic(char)
    }

    fun writeSetDateTime(epochSeconds: Long) {
        val json = "{\"epoch\": $epochSeconds}"
        writeCharacteristic(CHAR_SET_DATETIME, json.toByteArray())
    }

    fun writeMarquee(text: String, durationS: Int, speedMs: Int) {
        val safeText = text.replace("\"", "'")
        val json = "{\"text\": \"$safeText\", \"duration_s\": $durationS, \"speed_ms\": $speedMs}"
        writeCharacteristic(CHAR_MARQUEE, json.toByteArray())
    }

    fun writeConfig(tempUnit: String) {
        val json = "{\"temp_unit\": \"$tempUnit\"}"
        writeCharacteristic(CHAR_CONFIG, json.toByteArray())
    }

    @Suppress("MissingPermission")
    fun readConfig() {
        val g = gatt ?: return
        val char = findCharacteristic(CHAR_CONFIG) ?: return
        g.readCharacteristic(char)
    }

    @Suppress("MissingPermission")
    private fun enableStatusNotifications() {
        val g = gatt ?: return
        val char = findCharacteristic(CHAR_STATUS) ?: return
        g.setCharacteristicNotification(char, true)
        val descriptor = char.getDescriptor(CCCD_UUID) ?: return
        @Suppress("DEPRECATION")
        descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        @Suppress("DEPRECATION")
        g.writeDescriptor(descriptor)
    }

    private fun log(msg: String) {
        Log.d(TAG, msg)
        onLog?.invoke(msg)
    }
}
