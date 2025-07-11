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

## Supported entities

The integration uses the following entities to enable monitoring and control of individual components of the Jablotron
ecosystem:

| Entity type           | Description                                                     |
|-----------------------|-----------------------------------------------------------------|
| `alarm_control_panel` | Used for monitoring and controlling alarm sections              |
| `binary_sensor`       | Used for monitoring **UN**controllable programmable gates (PGs) |
| `switch`              | Used for controlling programmable gates (PGs)                   |
| `sensor`              | Used for monitoring temperature sensors                         |

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

## Missing functionality

* Integration does not listen for active alarms **- this is limitation of Jablotron Cloud API**