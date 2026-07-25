package com.relogioesp32.ble

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.relogioesp32.ble.databinding.ActivityMainBinding
import java.util.TimeZone

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var ble: BleManager

    private val requestPermissionsLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        if (results.values.all { it }) {
            ble.startScan()
        } else {
            appendLog("Permissoes negadas - nao e possivel usar Bluetooth.")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val versionName = packageManager.getPackageInfo(packageName, 0).versionName
        appendLog("App versao: $versionName")

        ble = BleManager(applicationContext)
        ble.onLog = { msg -> runOnUiThread { appendLog(msg) } }
        ble.onConnectionStateChange = { connected ->
            runOnUiThread {
                binding.textConnectionStatus.text = if (connected) "Conectado" else "Desconectado"
            }
        }
        ble.onStatusChanged = { json -> runOnUiThread { binding.textStatus.text = json } }
        ble.onConfigRead = { json -> runOnUiThread { binding.textConfig.text = json } }

        binding.buttonConnect.setOnClickListener { requestPermissionsAndScan() }

        binding.buttonSyncTime.setOnClickListener {
            // O firmware nao faz conversao de fuso horario (ver SPECS.md
            // secao 2.3/4.2) - por isso enviamos o epoch ja deslocado pelo
            // fuso local, para o RTC do ESP32 exibir a hora certa da regiao.
            val nowUtcMillis = System.currentTimeMillis()
            val offsetMillis = TimeZone.getDefault().getOffset(nowUtcMillis)
            val localEpochSeconds = (nowUtcMillis + offsetMillis) / 1000
            ble.writeSetDateTime(localEpochSeconds)
        }

        binding.buttonSendMarquee.setOnClickListener {
            val text = binding.editMarqueeText.text.toString()
            val duration = binding.editMarqueeDuration.text.toString().toIntOrNull() ?: 30
            val speed = binding.editMarqueeSpeed.text.toString().toIntOrNull() ?: 300
            ble.writeMarquee(text, duration, speed)
        }

        binding.buttonSaveConfig.setOnClickListener {
            val unit = if (binding.radioFahrenheit.isChecked) "F" else "C"
            ble.writeConfig(unit)
        }

        binding.buttonReadConfig.setOnClickListener { ble.readConfig() }
    }

    private fun requestPermissionsAndScan() {
        val adapter = BluetoothAdapter.getDefaultAdapter()
        if (adapter == null || !adapter.isEnabled) {
            appendLog("Ative o Bluetooth do celular primeiro.")
            return
        }

        val needed = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

        val allGranted = needed.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }

        if (allGranted) {
            ble.startScan()
        } else {
            requestPermissionsLauncher.launch(needed)
        }
    }

    private fun appendLog(msg: String) {
        binding.textLog.append("\n$msg")
    }

    override fun onDestroy() {
        ble.disconnect()
        super.onDestroy()
    }
}
