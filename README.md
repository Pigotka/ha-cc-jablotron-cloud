![Home_Assistant](https://img.shields.io/badge/Home-Assistant-blue)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub](https://img.shields.io/github/license/viktak/ha-cc-openweathermap_all)

[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20us%20a%20coffee-green.svg?style=for-the-badge)](https://www.buymeacoffee.com/michalbartP)

![Jablotron logo](https://github.com/Pigotka/ha-cc-jablotron-cloud/blob/main/logo.png)


# Jablotron Cloud

HACS custom component for jablotron cloud integration


## About

Integration works with MyJablotron web service available on https://www.jablonet.net/. It uses mobile API provided by [JablotronPy](https://github.com/fdegier/JablotronPy) library. It does not have full capabilities of web interface and some function are not yet supported by the integration. See the list of supported function below.

**This component will set up the following platforms.**

| Platform         | Description                         |
| ---------------- | ----------------------------------- |
| `binary_sensor`| To show uncontrollable programmable gates (PG) .   |
| `switch`| To controll programmable gates (PG) .   |
| `alarm_control_panel`| To enable ARM/DISARM on individual sections. |
| `sensor`| To support temperature and electricity sensors. |

## HACS Installation

1. Add repository using "+Explore & download repositories" button in HACS inside integrations section
2. Search for Jablotron Cloud in HACS
3. Install
4. In HA add new integration and select Jablotron Cloud.

## Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `jablotron_cloud`.
4. Download _all_ the files from the `custom_components/jablotron_cloud/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Jablotron Cloud"

## Configuration is done in the UI

To configure integration please fill credentials you use to access your MyJablotron web page or mobile app.

**Following fields needs to be filled:**

| Field         | Description                         |
| ---------------- | ----------------------------------- |
| `username` | Email associated with Jablotron cloud.   |
| `password` | Password use to login into the webpage. |

## Supported functionality

1. Programmable gates - show status of every programmable gate in your system. PG can be created to signal any state you like by your Jablotron provider. It can indicate you for example that section is armed or that it is armed only partially. It can also tell you state of you garage door or window contact sensors. Most of PG's can be controlled to trigger some Jablotron action.
2. Sections - every section is individual alarm control panel as it requires PIN codes to control it and can be ARMED (Armed Away) or PARTIALLY ARMED (Armed Home). Section also support friendly names defined in you cloud installation.
3. Default pin code - it can be configured in alarm entity options. Once configured code will become optional parameter for arm service.

## Known issues

1. Data are updated only every 30s
2. Arming and disarming has no delay to leave the house.
3. First entity get it's real state ony after 30s. Then it works like any other entity.
4. Integration does not listen for active alarms
5. Arming is always with FORCE param overriding any periphery error. This should be converted into user option.

## Missing functionality - will be added

1. Impulse counters
2. Alarm event detection

# Support

![Jablotron logo](https://github.com/Pigotka/ha-cc-jablotron-cloud/blob/main/bmc_qr.png)
