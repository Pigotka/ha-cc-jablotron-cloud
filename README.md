![Home Assistant](https://img.shields.io/badge/Home-Assistant-blue?style=for-the-badge)
![HACS](https://img.shields.io/badge/HACS-Integration-blue?style=for-the-badge)
![GitHub license](https://img.shields.io/github/license/Pigotka/ha-cc-jablotron-cloud?style=for-the-badge)

[![Buy me a coffee](https://img.shields.io/badge/buy_me_a_coffee-orange?style=for-the-badge&logo=buy-me-a-coffee&logoColor=white)](https://www.buymeacoffee.com/michalbartP)

---

![Jablotron logo](https://github.com/Pigotka/ha-cc-jablotron-cloud/blob/main/logo.png)

# Jablotron Cloud

Home Assistant custom component for Jablotron Cloud.

## About

This integration allows you to monitor and control alarm sections as well as programmable gates and temperature sensors.
It does not require a direct connection to the alarm control panel to run, instead it uses a cloud connection via
MyJablotron and takes advantage of the mobile API provided by the [JablotronPy](https://github.com/fdegier/JablotronPy)
library.

# Support

![Buy me a coffee QR](https://github.com/Pigotka/ha-cc-jablotron-cloud/blob/main/bmc_qr.png)

## Supported entities

The integration uses the following entities to enable monitoring and control of individual components of the Jablotron
ecosystem:

| Entity type           | Description                                                     |
|-----------------------|-----------------------------------------------------------------|
| `alarm_control_panel` | Used for monitoring and controlling alarm sections (including `triggered` state when an alarm is active) |
| `binary_sensor`       | Used for monitoring **UN**controllable programmable gates (PGs), and for reporting section bypasses |
| `climate`             | Used for controlling thermo devices (thermostats)               |
| `switch`              | Used for controlling programmable gates (PGs)                   |
| `sensor`              | Used for monitoring temperature sensors and non-controllable section states |

## HACS Installation

This integration can be installed using HACS, this can be achieved as follows:

1. Install and open HACS in Home Assistant
2. Search for `Jablotron Cloud`
3. Open it and click on `Download` button
4. In Home Assistant go to Integrations
5. Click on `Add integration` button
6. Search for `Jablotron Cloud`
7. Complete configuration and confirm

## Manual Installation

If you are not using HACS, you can install this integration manually as follows:

1. Open Home Assistant installation configuration directory (you should see `configuration.yaml` file)
2. Create `custom_components` folder, or skip this step if already exists
3. Open `custom_components` folder
4. Download `custom_components/jablotron_cloud` folder from this repository
5. Place downloaded `jablotron_cloud` folder to created `custom_components` folder
6. Restart Home Assistant
7. In Home Assistant go to Integrations
8. Click on `Add integration` button
9. Search for `Jablotron Cloud`
10. Complete configuration and confirm

## Integration configuration

To successfully set up this integration, you will need the username (email) and password used for the MyJablotron web
service/mobile app.

The integration allows you to modify the following parameters:

* Default pin used to control PGs
* Whether to bypass section errors by default when arming sections
* Frequency of polling data from Jablotron Cloud
* Timeout for polling data from Jablotron Cloud

## Section bypass (arming with an open door or window)

Arming a section whose detectors are not all closed requires a bypass - the confirmation the
MyJablotron app shows before it lets you arm anyway. This integration reproduces that flow in two
steps:

1. The section is armed normally. When every detector is closed nothing else happens, so a clean
   arm still costs a single request.
2. When the cloud answers with a `BYPASS-TIMED` (or `BYPASS`) control error, active devices are
   blocking the section. If *Bypass section errors* is enabled the request is repeated with the
   bypass confirmed and the bypass is reported to Home Assistant. If it is disabled the arm fails
   with the cloud error, exactly as before.

> **Note on the payload.** The `force` flag is only honoured by the cloud when it sits inside the
> request's `actions` object. [JablotronPy](https://github.com/fdegier/JablotronPy) 0.7.4 places it
> next to `component-id`, where it is silently ignored, so arming a section with an open window
> always failed with `BYPASS-TIMED` regardless of configuration. This integration therefore builds
> the section control payload itself instead of calling `control_section()`.

### Bypass entities and events

Every controllable section gets a `binary_sensor` bypass indicator. It turns `on` for 30 seconds
after an arm that required a bypass and then clears itself, which makes it convenient for firing a
notification or a dashboard pop-up. The attributes describe the most recent bypass and remain
readable after the sensor clears:

| Attribute       | Description                                              |
|-----------------|----------------------------------------------------------|
| `section_name`  | Name of the section that was armed                        |
| `section_id`    | Cloud component id of the section, e.g. `SEC-8902238`     |
| `control_error` | Code reported by the cloud, e.g. `BYPASS-TIMED`           |
| `bypassed_at`   | ISO 8601 timestamp of the bypass                          |

The same payload is fired on the event bus as `jablotron_cloud_section_bypassed`, carrying
`service_id`, `service_name`, `section_id`, `section_name` and `control_error`.

```yaml
- alias: Jablotron armed with a bypass
  trigger:
    - platform: event
      event_type: jablotron_cloud_section_bypassed
  action:
    - service: notify.mobile_app
      data:
        title: "Armed with bypass"
        message: >-
          Section {{ trigger.event.data.section_name }} was armed while devices were active.
```

### Which device caused the bypass?

**The cloud does not say, and it cannot be derived from the API.** The bypass error identifies the
section only. There is no endpoint that lists detectors: `peripheralsGet`, `devicesGet` and
`deviceStatesGet` all answer `FUNCTION.NOT-FOUND`, and `eventHistoryGet` answers
`METHOD.NOT-SUPPORTED` on several panels. The mobile API exposes sections, PGs, thermo devices and
keyboard segments and nothing below them.

If you want to name the door or window, correlate the section with your own contact sensors:

```yaml
- alias: Show which window forced the bypass
  trigger:
    - platform: event
      event_type: jablotron_cloud_section_bypassed
  action:
    - service: notify.mobile_app
      data:
        title: "Armed with bypass"
        message: >-
          {% set open = states.binary_sensor
               | selectattr('attributes.device_class', 'in', ['window', 'door'])
               | selectattr('state', 'eq', 'on') | map(attribute='name') | list %}
          {{ trigger.event.data.section_name }} armed. Open: {{ open | join(', ') or 'unknown' }}
```

## Alarm event detection

The integration surfaces an active alarm by flipping the affected `alarm_control_panel` entity to the
`triggered` state. Detection is **per section** — when an alarm is in progress, the Jablotron Cloud API
returns an event with a message such as `"Alarm - Periphery PIR chodba (wifi), Section Dům"`. The
integration parses the section name from the substring after the `, Section ` token and only the matching
section is reported as `triggered`. Other sections of the same service stay in their previous state.

While a section is `triggered`, its entity exposes the following extra attributes describing the latest
matching event:

| Attribute            | Description                                                          |
|----------------------|----------------------------------------------------------------------|
| `last_alarm_type`    | Event type as reported by the cloud (currently always `ALARM`)       |
| `last_alarm_message` | Human-readable description, e.g. detector and section that triggered |
| `last_alarm_date`    | ISO 8601 timestamp when the event was raised                         |

Example automation that fires whenever any alarm panel is triggered:

```yaml
- alias: Jablotron alarm triggered
  trigger:
    - platform: state
      entity_id: alarm_control_panel.dum
      to: "triggered"
  action:
    - service: notify.mobile_app
      data:
        title: "Alarm!"
        message: "{{ state_attr(trigger.entity_id, 'last_alarm_message') }}"
```

### Caveats

* **Polling-based detection.** The Jablotron Cloud API does not push notifications. The integration only
  knows about an alarm while the cloud response still contains the active event. If the alarm is silenced
  before the next poll, the trigger is missed. For time-critical automations consider lowering the
  `Frequency of polling` setting (minimum 30 seconds).
* **Message format dependency.** Section identification relies on the message ending with
  `, Section <name>` where `<name>` matches the configured section name exactly. If your panel firmware
  emits ALARM events without that suffix, the entity will not flip to `triggered`. Please open an issue
  with a redacted log sample if you observe this.
* **Historical events are not used.** The cloud-side event history endpoint (`eventHistoryGet`) returns
  `400 METHOD.NOT-SUPPORTED` on several panel models (e.g. JA100F), so it is not relied on as a fallback.


