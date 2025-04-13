# YIP Daikin FCU Integration

This custom integration allows Home Assistant to control Daikin fan coil units (FCUs) over MQTT using the proprietary protocol.

## Features

- Decode MQTT payloads from FCUs (broadcast/read)
- Control on/off, HVAC mode, fan speed, swing, temperature
- Frame validation using Longitudinal Redundancy Check (LRC)

## Installation

1. Copy this repo into `config/custom_components/yip_daikin_fcu`
2. Restart Home Assistant
3. Configure via UI (Settings > Devices & Services > Add Integration)

## MQTT Topic Structure

- Broadcast: `<location>/<proto>/broadcast/device/<mac>`
- Response:  `<location>/<proto>/response/app/+/device/<mac>`
- Command:   `<location>/<proto>/query/device/<mac>/app/<app_name>`

## Example

```yaml
climate:
  - platform: yip_daikin_fcu
    mac: "600194657C39"
    location: "trainingcenter"
    protocol_prefix: "daikiniot"
    app_name: "homeassistant-yip_daikin_fcu"
