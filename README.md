# turboenergysolarinverter

This Python script extracts information from the inverter via rs485 serial line (Modbus RTU) and sends it to an MQTT broker.

Modbus TCP should work but has not been tested.

Tested on a Turbo Energy 5.5Kw

Should be compatible with Deye and Sunsynk versions.


Home Asisstant:
   - You need an MQTT Broker.
   - Add the content of the configuration.yaml to your Home Assistant configuration.yaml and restart.
   - Configure the Energy panel with the following entities:
      - TurboE Total Grid Buy Power
      - TurboE Total Grid Sell Power 
      - TurboE Hist PV Power
      - TurboE Total Battery Charge Power
      - TurboE Total Battery Discharge Power


Energy panel sample:

![Energy Panel](20220420002744.jpg)


Sample panel with many cards:

![Energy Panel](20220420002703.jpg)

