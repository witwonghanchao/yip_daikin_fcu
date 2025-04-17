# custom_components/yip_daikin_fcu/climate.py
"""
  Daikin FCU Home Assistant Climate Integration (via MQTT)
  https://github.com/witwonghanchao/yip_daikin_fcu

  Description:
    This custom integration enables Home Assistant to control and monitor Daikin fan coil units (FCUs)
    via MQTT using a decoded proprietary frame protocol. It supports both decoding telemetry from FCUs
    and sending control commands (e.g., power, mode, temperature, fan speed, swing).

  Features:
    - Listens for MQTT BROADCAST and READ responses from each Daikin FCU
    - Parses and validates payloads using Longitudinal Redundancy Check (LRC)
    - Updates Home Assistant climate state from decoded values:
        - Power, mode, set temperature, room temperature, fan speed, sweep (swing)
    - Supports climate control via UI or automation:
        - On/off, set temperature, HVAC mode, fan mode, swing mode
    - Publishes MQTT write commands using the documented protocol frame
    - Cleanly subscribes/unsubscribes on integration load/unload

  Supported MQTT Topics:
    - [broadcast] <location>/<proto>/broadcast/device/<mac>
    - [response]  <location>/<proto>/response/app/+/device/<mac>
    - [command]   <location>/<proto>/query/device/<mac>/app/<app_name>

  Example:
    Broadcast Topic:
      trainingcenter/daikiniot/broadcast/device/600194657C39
    Response Topic:
      trainingcenter/daikiniot/response/app/wit-mqtt/device/600194657C39
    Command Topic:
      trainingcenter/daikiniot/query/device/600194657C39/app/homeassistant-yip_daikin_fcu

  Example Frame:
    {600194657C39000000001515000406000507280000012C01C80085EEEE003030304F53}

  Notes:
    - Frame LRC is checked before decoding; invalid frames are skipped
    - Fan speeds, sweep modes, and modes are mapped using known hex → text values
    - Designed to work with Tasmota or ESPHome-based MQTT bridges with Daikin protocol

  GitHub:
    https://github.com/witwonghanchao/yip_daikin_fcu

  Version History:
    2025.04.13 - Wit Wonghanchao
      - HA-aligned structure with logical grouping
      - LRC decode refactored
      - Fan mode compatibility fix and unsubscribe handling

    2025.04.10 - Wit Wonghanchao
      - Fully working feature set: on/off, mode, temp, fan, swing
      - MQTT topic structure cleanup
"""


import logging
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.components import mqtt

# --- Constants ---
DOMAIN = "yip_daikin_fcu"
DEFAULT_MIN_TEMP = 16
DEFAULT_MAX_TEMP = 30
DEFAULT_TEMPERATURE_UNIT = UnitOfTemperature.CELSIUS

FAN_SPEED_MAP = {
    3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 10: "AUTO", 255: "AUTO"
}

SWING_MAP = {
    0: "SWEEP ON", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 8: "AUTO", 255: "AUTO"
}

MODE_MAP = {
    0: "fan_only",
    1: "cool",
    2: "dry",
}

_LOGGER = logging.getLogger(__name__)


# --- Frame + Command Utilities ---
def calculate_lrc(data: bytes) -> int:
    return (0xFF - (sum(data) % 256) + 1) % 256

def validate_lrc_from_frame(frame: str) -> bool:
    try:
        byte_count_hex = frame[22:26]
        byte_count = int(byte_count_hex[2:4] + byte_count_hex[0:2], 16)
        data_end = 26 + byte_count * 2
        data_bytes = bytes.fromhex(frame[:data_end])
        received_lrc = frame[data_end:data_end + 2]
        calc_lrc = calculate_lrc(data_bytes)
        return f"{calc_lrc:02X}" == received_lrc.upper()
    except Exception:
        return False

def build_payload(mac: str, function: str, start_reg: str, reg_count: str, data: str) -> str:
    mac = mac.upper().replace(":", "").replace("-", "")
    header = mac + "0000" + function + start_reg + reg_count
    byte_count = len(data) // 2
    byte_count_lo = byte_count % 256
    byte_count_hi = byte_count // 256
    byte_count_hex = f"{byte_count_lo:02X}{byte_count_hi:02X}"
    payload_base = bytes.fromhex(header + byte_count_hex + data)
    lrc = calculate_lrc(payload_base)
    return f"({header}{byte_count_hex}{data}{lrc:02X})"


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    entity = YipDaikinFCUClimate(entry.entry_id, data)
    async_add_entities([entity])
    _LOGGER.debug("[SETUP] Climate entity added: %s", data.get("device_name", "unknown"))


# --- Main Climate Entity Class ---
class YipDaikinFCUClimate(ClimateEntity):
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.FAN_ONLY, HVACMode.DRY]
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_target_temperature_step = 1.0
    _attr_fan_modes = ["3", "4", "5", "6", "7", "AUTO"]
    _attr_swing_modes = ["SWEEP ON", "1", "2", "3", "4", "5", "AUTO"]

    def __init__(self, entry_id, config):
        self._entry_id = entry_id
        self._config = config
        self._attr_name = config.get("device_name", "Unnamed FCU")
        self._attr_unique_id = config.get("mac")
        self._attr_extra_state_attributes = {
            "mac": config.get("mac"),
            "location": config.get("location"),
            "protocol_prefix": config.get("protocol_prefix"),
            "app_name": config.get("app_name"),
        }
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 25.0
        self._attr_current_temperature = 27.0
        self._attr_fan_mode = "AUTO"
        self._attr_swing_mode = "SWEEP ON"
        self._unsub_listeners = []

    # --- Lifecycle ---
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        mac = self._config.get("mac")
        location = self._config.get("location")
        proto = self._config.get("protocol_prefix")
        topics = [
            f"{location}/{proto}/broadcast/device/{mac}",
            f"{location}/{proto}/response/app/+/device/{mac}"
        ]

        @callback
        def message_received(msg):
            try:
                _LOGGER.debug("[%s] 🔔 message_received topic: %s", self.name, msg.topic)
                payload = msg.payload if isinstance(msg.payload, str) else msg.payload.decode(errors="ignore")
                _LOGGER.debug("[%s] 📩 Raw payload: %s", self.name, payload)
                result = self._decode_daikin_frame(payload)
                if result:
                    _LOGGER.debug("[%s] ✅ Decoded frame: %s", self.name, result)
                    self._update_state_from_decoded(result)
                    self.async_write_ha_state()
            except Exception as e:
                _LOGGER.exception("[%s] ❌ Exception in message_received: %s", self.name, e)

        for topic in topics:
            _LOGGER.debug("[%s] 📡 Subscribing to: %s", self.name, topic)
            unsub = await mqtt.async_subscribe(self.hass, topic, message_received)
            self._unsub_listeners.append(unsub)

    async def async_will_remove_from_hass(self):
        _LOGGER.debug("[%s] 🔻 Unsubscribing from MQTT topics", self.name)
        for unsub in self._unsub_listeners:
            unsub()

    # --- Decoding & State ---
    def _decode_daikin_frame(self, payload_str):
        _LOGGER.debug("[%s] 🔍 Decoding frame...", self.name)
        if not payload_str.startswith("{") or not payload_str.endswith("}"):
            return None
        frame = payload_str.strip("{}")
        if len(frame) < 30:
            return None
        if not validate_lrc_from_frame(frame):
            _LOGGER.warning("[%s] ❌ Invalid LRC in frame", self.name)
            return None

        try:
            byte_count_hex = frame[22:26]
            byte_count = int(byte_count_hex[2:4] + byte_count_hex[0:2], 16)
            data_hex = frame[26:26 + byte_count * 2]

            def to_int(offset): return int(data_hex[offset:offset+2], 16)

            return {
                "power": to_int(4),
                "fan_speed": to_int(8),
                "set_temp": to_int(10) / 2,
                "sweep_status": to_int(14),
                "mode": to_int(16),
                "room_temp": (256 * to_int(20) + to_int(18)) / 10.0,
            }
        except Exception as e:
            _LOGGER.warning("[%s] ❌ Decode failed: %s", self.name, e)
            return None

    def _update_state_from_decoded(self, decoded):
        power = decoded.get("power")
        mode = decoded.get("mode")
        set_temp = decoded.get("set_temp")
        room_temp = decoded.get("room_temp")
        fan_speed = decoded.get("fan_speed")
        sweep_status = decoded.get("sweep_status")

        _LOGGER.debug("[%s] 🔄 State update: power=%s, mode=%s, set_temp=%s, room_temp=%s",
                      self.name, power, mode, set_temp, room_temp)

        if power == 1:
            self._attr_hvac_mode = {
                0: HVACMode.FAN_ONLY,
                1: HVACMode.COOL,
                2: HVACMode.DRY
            }.get(mode, HVACMode.OFF)
        else:
            self._attr_hvac_mode = HVACMode.OFF

        if set_temp is not None:
            self._attr_target_temperature = set_temp
        if room_temp is not None:
            self._attr_current_temperature = room_temp

        self._attr_fan_mode = FAN_SPEED_MAP.get(fan_speed, str(fan_speed))
        self._attr_swing_mode = SWING_MAP.get(sweep_status, str(sweep_status))

    # --- User Control ---
    async def async_turn_on(self):
        _LOGGER.debug("[%s] 🔛 Turning ON (async_turn_on)", self.name)
        await self._send_power_command(turn_on=True)

    async def async_turn_off(self):
        _LOGGER.debug("[%s] 🔴 Turning OFF (async_turn_off)", self.name)
        await self._send_power_command(turn_on=False)

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is not None:
            _LOGGER.debug("[%s] 🌡️ Set temperature to: %s°C", self.name, temp)
            await self._send_write_command("05", f"{int(temp * 2):02X}")

    async def async_set_hvac_mode(self, hvac_mode: str):
        _LOGGER.debug("[%s] ⚙️ Set HVAC mode to: %s", self.name, hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self._send_power_command(turn_on=False)
            return

        mode_hex = {
            HVACMode.FAN_ONLY: "00",
            HVACMode.COOL: "01",
            HVACMode.DRY: "02",
        }.get(hvac_mode)

        if mode_hex is None:
            _LOGGER.warning("[%s] ⚠️ Unsupported HVAC mode: %s", self.name, hvac_mode)
            return

        await self._send_write_command("08", mode_hex)
        await asyncio.sleep(0.3)
        await self._send_power_command(turn_on=True)
        self._attr_hvac_mode = hvac_mode

    async def async_set_fan_mode(self, fan_mode: str):
        fan_hex = "0A" if fan_mode.upper() == "AUTO" else f"{int(fan_mode):02X}"
        _LOGGER.debug("[%s] 💨 Set fan_mode to: %s (hex: %s)", self.name, fan_mode, fan_hex)
        await self._send_write_command("04", fan_hex)

    async def async_set_swing_mode(self, swing_mode: str):
        swing_hex = {
            "SWEEP ON": "00",
            "1": "01", "2": "02", "3": "03", "4": "04", "5": "05",
            "AUTO": "08"
        }.get(swing_mode.upper(), "00")
        _LOGGER.debug("[%s] 🌀 Set swing_mode to: %s (hex: %s)", self.name, swing_mode, swing_hex)
        await self._send_write_command("07", swing_hex)

    # --- Command Senders ---
    async def _send_power_command(self, turn_on: bool):
        value = "01" if turn_on else "00"
        await self._send_write_command("02", value)

    async def _send_write_command(self, reg: str, hex_data: str):
        mac = self._config.get("mac")
        location = self._config.get("location")
        proto = self._config.get("protocol_prefix")
        app = self._config.get("app_name")
        topic = f"{location}/{proto}/query/device/{mac}/app/{app}"
        payload = build_payload(mac, "01", reg, "01", hex_data)
        _LOGGER.debug("[%s] 🚀 Sending command to topic %s: %s", self.name, topic, payload)
        await mqtt.async_publish(self.hass, topic, payload)

