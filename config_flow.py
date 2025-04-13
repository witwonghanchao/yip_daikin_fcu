import voluptuous as vol
import socket
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    CONF_MAC,
    CONF_LOCATION,
    CONF_PROTOCOL_PREFIX,
    CONF_APP_NAME,
)

class YipDaikinFCUConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for YIP Daikin FCU."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the setup form to the user."""
        errors = {}

        if user_input is not None:
            mac = user_input[CONF_MAC]

            # Auto-generate app name with hyphen
            hostname = socket.gethostname()
            user_input[CONF_APP_NAME] = f"{hostname}-yip_daikin_fcu"

            await self.async_set_unique_id(mac.lower())
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_DEVICE_NAME],
                data=user_input,
            )

        schema = vol.Schema({
            vol.Required(CONF_DEVICE_NAME, default="Y165"): str,
            vol.Required(CONF_MAC, default="68C63A8EA465"): str,
            vol.Required(CONF_LOCATION, default="trainingcenter"): str,
            vol.Required(CONF_PROTOCOL_PREFIX, default="daikiniot"): str
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )
