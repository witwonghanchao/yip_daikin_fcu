# YIP Daikin FCU

A Home Assistant custom integration for controlling Daikin fan coil units (FCUs) over MQTT using a proprietary hex frame protocol with LRC validation.

This integration is developed and maintained by [Wit Wonghanchao](https://github.com/witwonghanchao) as part of the YIP IoT Platform initiative.

---

## 🌟 Features

- ✅ Real-time MQTT decoding of Daikin FCU broadcast and response frames
- ✅ Control power, temperature, HVAC mode, fan speed, and swing mode
- ✅ Longitudinal Redundancy Check (LRC) validation for all incoming frames
- ✅ Supports Tasmota/ESP-based MQTT bridges or ThingsBoard MQTT routing
- ✅ Fully compatible with Home Assistant's Climate UI and automations
- ✅ Clean entity creation and MQTT subscription management

---

## 📦 Installation

1. Copy this repository into your Home Assistant config directory:

   ```
   /config/custom_components/yip_daikin_fcu/
   ```

2. Make sure your `manifest.json` and `climate.py` are present, along with any translations.

3. Restart Home Assistant.

4. Add the integration via **Settings → Devices & Services → Add Integration**, or use YAML (see below).

---

## 🥉 Configuration (YAML Example)

```yaml
climate:
  - platform: yip_daikin_fcu
    mac: "600194657C39"
    location: "trainingcenter"
    protocol_prefix: "daikiniot"
    app_name: "homeassistant-yip_daikin_fcu"
```

Each FCU must be defined with its:
- `mac`: MAC address of the FCU (12-char uppercase)
- `location`: Base MQTT path prefix
- `protocol_prefix`: Path under location
- `app_name`: Your Home Assistant's identity in MQTT command topics

---

## 📡 MQTT Topics Used

### ➔ Broadcast (status push from FCU)
```
<location>/<protocol>/broadcast/device/<mac>
```

### ➔ Response (reply to a request)
```
<location>/<protocol>/response/app/<app>/device/<mac>
```

### ➔ Command (send write/read request)
```
<location>/<protocol>/query/device/<mac>/app/<app>
```

---

## 🔁 Example Frame

```
{600194657C39000000001515000406000507280000012C01C80085EEEE003030304F53}
```

### Frame Format:
- `{` `}` = Start/End markers
- LRC = Longitudinal Redundancy Check for validation
- Data payload decoded to:
  - Power: ON/OFF
  - Mode: COOL/FAN/DRY
  - Fan speed
  - Swing (sweep)
  - Room temp
  - Target temp

---

## ✅ Supported Features

- `HVAC Modes`: `off`, `cool`, `fan_only`, `dry`
- `Fan Modes`: `3`, `4`, `5`, `6`, `7`, `AUTO`
- `Swing Modes`: `SWEEP ON`, `1`–`5`, `AUTO`
- `Temperature Range`: `16°C` to `30°C` (in 1.0°C steps)

---

## 🧠 Protocol Notes

- Payloads are proprietary hex strings from Daikin FCUs
- Integration uses `LRC` = `(0xFF - (sum of bytes % 256) + 1) % 256`
- Invalid frames are automatically ignored
- Decoding supports both BROADCAST and READ responses

---

## 🛠️ Development

This project is developed under:

- Python 3.11+
- Home Assistant Core >= 2024.2
- MQTT-based architecture
- Local Push (`iot_class: local_push`)

---

## 🔪 Testing & Validation

A `hassfest` GitHub workflow is provided in `.github/workflows/hassfest.yml` to validate integration structure.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

© 2025 Wit Wonghanchao / YIP IoT Platform

