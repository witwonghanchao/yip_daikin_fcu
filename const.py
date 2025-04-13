DOMAIN = "yip_daikin_fcu"

CONF_DEVICE_NAME = "device_name"
CONF_MAC = "mac"
CONF_LOCATION = "location"
CONF_APP_NAME = "app_name"
CONF_PROTOCOL_PREFIX = "protocol_prefix"

DEFAULT_TEMPERATURE_UNIT = "C"
DEFAULT_MIN_TEMP = 16
DEFAULT_MAX_TEMP = 32

# Topic templates (protocol_prefix = e.g., "daikiniot")
TOPIC_BROADCAST = "{location}/{protocol_prefix}/broadcast/device/{mac}"
TOPIC_QUERY = "{location}/{protocol_prefix}/query/device/{mac}/app/{app_name}"
TOPIC_RESPONSE = "{location}/{protocol_prefix}/response/app/{app_name}/device/{mac}"
