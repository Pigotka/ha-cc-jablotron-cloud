![Home_Assistant](https://img.shields.io/badge/Home-Assistant-blue) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs) ![GitHub](https://img.shields.io/github/license/viktak/ha-cc-openweathermap_all)

![Jablotron logo](https://github.com/Pigotka/ha-cc-jablotron-cloud/logo.png)


# Jablotron Cloud
HACS custom component for jablotron cloud integration


## About
Integration works with MyJablotron web service available on https://www.jablonet.net/. It uses mobile API provided by JablotronPy library. It does not have full capabilities of web interface and some function are not yet supported by the integration. See the list of supported function below.

**This component will set up the following platforms.**

| Platform         | Description                         |
| ---------------- | ----------------------------------- |
| `binary_sensor`| To show programmable gates (PG) .   |
| `alarm_control_panel`| To enable ARM/DISARM on individual secrions. |
| `sensor`| To support temperature and eletricity sensors TBD... |

## HACS Installation

1. Add this repository to "Custom repositories"
2. Add and search for Jablotron Clound in HACS
3. Install

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
| `pin` | Optional. If you configure your keyboard pin this pin will be automatically used to ARM/DISARM section. If you leave this field empty you will have to enter pin everytime you manipulate with sections. |

## Supported functionality

1. Programmable gates - show status of every programmable gate in your system. PG can be created to signal eny state you like by your Jablotron provider. It can indicate you for example that section is armed or that it is armed only partially. It can allso tell you state of you garage door or window contact sensors.
2. Sections - every section is individual alarm control panel as it requires PIN codes to controll it and can be ARMED (Armed Away) or PARTIALY ARMED (Armed Home). Section also support friendly names defined in you cloud installation.

## Known issues
1. Section state is reported as ARMED even thoung it is armed partially - this is how the API reports it and will be unlikely possible to fix. You can see partialy armed states in you list of PG's.
2. PG friendly names are not used. Although Jablotron webpage does show names of all components in human readable form the API version we are using right now does not provide names for PG's.
3. Data are updated only every 30s
4. Arming and disarming has no delay to leave the house.

## Missing functionality - will be added
1. Temperature and humidity sensors
2. Electricity sensors