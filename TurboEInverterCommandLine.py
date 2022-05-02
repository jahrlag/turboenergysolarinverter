#!/usr/bin/python3

###############################################
#
#	Este script es una PRUEBA DE CONCEPTO y puede no estar terminado.
#
#

###############################################
#
#	Author: Juan Andrés Hernández
#
#

###############################################
#
# Incompatibilidades conocidas y particularidades:
#
#	- Está probado con un inversor Turbo Energy 5Kw configurado en monofásica
#	- Lee dos bloques de direcciones (incluyendo posiciones de 59 a 284) en vez de leer los registros de uno en uno. Esto es así por velocidad.
#	  Si se necesita otra información fuera de ese rangohabría que modificar el programa.
#	- Solo publica los datos definidos en la clase inverterData
#
#

###############################################
# TODO (- = Req ; * = Working ; + = Done)
#
#	- Actualizar la hora según tu zona horaria.
#		Lo ideal es capturar un evento cuando cambie la hora, pero no sé hacerlo ni si se puede hacer.
#		Otra opción es comprobar la hora en cada lectura de menos frecuencia y compararla con la del inversor.
#	+ Que sea compatible con Home Assistant Energy
#	- Primero lo haré por mqtt. Investigar cómo hacerlo directamente sin mqtt.
#	* Add Modbus TCP.
#	- Clean the code and split in different files
#	- Run as a Home Assistant module
#	- Add a global variable indicating the las time the corresponding register set was readed from the inverter
#	- Add debug info.
#	- Should I close the connection to free the serial port or leave it open?
#	+ Si al publicar los datos de menos frecuencia hay error intentarlo en la siguiente iteración.
#	+ Round loat values
#	- Mostrar programación horaria
#
#


###############################################
#
# Load required libraries
#
import sys
import time
from pymodbus.client.sync import ModbusSerialClient
#from pyModbusTCP.client import ModbusTCPClient			# ModbusTPC not tested
import paho.mqtt.publish as publish

#
# Global 
#
version				=	"alpha-2022050201"	# Program Version
inverterConnection	=	ModbusSerialClient(method='rtu', port='/dev/ttyUSB0', baudrate=9600, timeout=3, parity='N', stopbits=1, bytesize=8)
#inverterConnection	=	ModbusTCPClient(host="192.168.115.150", port=502, unit_id=1, auto_open=True)	# ModbusTPC not tested
#MQTTBROKER			=	"192.168.1.2"
MQTTBROKER			=	"test.mosquitto.org"
MQTTPORT			=	1883
#MQTTUSER			=	"mqttuser"
MQTTUSER			=	""
#MQTTPASSW			=	"mqttpass"
MQTTPASSW			=	""
MQTTTOPIC			=	"solar/inversor/turboenergy/"
MQTTCLIENTID		=	"TurboEnergyData16487973615649784"	# Has to be unique


dataSet				=	[0]*2				# Inverter Registers from 59 to 172 and from 173 to 284
dataSet1From		=	59
dataSet1Size		=	113
dataSet2From		=	dataSet1From+dataSet1Size
dataSet2Size		=	113

# Loop mode dumps data continuously
loopMode			=	True

# Time in seconds beteen readings in loop mode
highRateDataDelay	=	10			# 0 = Run continuously
lowRateDataEvery	=	5


#
# Classes
#

# Defines a simple register. A register may contain data from multiple addresses.
class Register:
	registerName = ""
	baseAddress = 0
	sizeOfRegister = 0
	multiplier = 0
	unit = 0

	def __init__(self, registerName, baseAddress, sizeOfRegister, multiplier, unit):
		self.registerName = registerName
		self.baseAddress = baseAddress
		self.sizeOfRegister = sizeOfRegister
		self.multiplier = multiplier
		self.unit = unit

	# Return the usable value of the register or "NotValid"
	def getData(self):
		dataSetIndex = -1
		returnValue = ""
		#print("Obteniendo dato de ",self.registerName)
		#print("Obteniendo dato del índice: ", self.baseAddress)
		if self.baseAddress < dataSet2From:
			dataSetIndex = 0
			registerIndex = self.baseAddress - dataSet1From
			#print("DataSet1From: ",dataSet1From)
		else:
			dataSetIndex = 1
			registerIndex = self.baseAddress - dataSet2From
			#print("DataSet2From: ",dataSet2From)

		#print("dataSetindex ", dataSetIndex)
		#print("registerIndex ", registerIndex)

		if dataSet[dataSetIndex].isError():
			returnValue = "NotValid"
		else:
			if self.sizeOfRegister == 1:
				#print("Dato con una dirección")
				returnValue = dataSet[dataSetIndex].registers[registerIndex]

				# Humanize Running State values.
				if self.baseAddress == 59:
					if returnValue == 0:
						returnValue = "Stand By"
					elif returnValue == 1:
						returnValue = "Self Checking"
					elif returnValue == 2:
						returnValue = "Normal"
					elif returnValue == 3:
						returnValue = "Fault"

				# Temperatures are calculated as data-1000 in register. 1000 = 0ºC. Add them on this list
				if self.baseAddress in [90, 91, 95, 182]:
					returnValue = returnValue - 1000
				# Some values are represented as signed int
				if self.baseAddress in [190, 191, 172]:
					if returnValue > 32767:
						#print(self.baseAddress)
						returnValue -= 65535
				returnValue *= self.multiplier

				# Humanize Grid Side Relay Status
				if self.baseAddress in [194]:
					if returnValue == 1:
						returnValue = "on"
					elif returnValue == 0:
						returnValue = "off"
					else:
						returnValue = "unknown"

				# Humanize Time of Use Selling
				if self.baseAddress == 248:
					if (returnValue & int("11111111",2)) == 0xFF:
						returnValue = "on"
					elif (returnValue & int("11111111",2)) == 0x00:
						returnValue = "off"
					# Time of Use Selling dumpt the time table too
					#returnValue = [returnValue, "linea 1", "linea 2", "linea 3", "linea 4", "linea 5", "linea 6" ]
					

				# Humanize Grid Mode
				if self.baseAddress == 284:
					if returnValue == 0:
						returnValue = "General_Standard"
					elif returnValue == 1:
						returnValue = "UL1741&IEE1547"
					elif returnValue == 2:
						returnValue = "CPUC_RULE21"
					elif returnValue == 3:
						returnValue = "SRD-UL1741"


			# 
			if self.sizeOfRegister == 2:
				#print("Datos con dos direcciones")
				#print("Primera palabra ",dataSet[dataSetIndex].registers[registerIndex])
				returnValue = dataSet[dataSetIndex].registers[registerIndex]
				nextAddress = 1
				# Some values are not in consecutive addresses. Add them on this list
				if self.baseAddress in [78]:
					#print("Dos registros no contínuos")
					nextAddress = 2
				# Values are usually in consecutive registers
				else:
					nextAddress = 1
					#print("Dos registros contínuos")

				#print("Segunda palabra ",dataSet[dataSetIndex].registers[registerIndex+nextAddress])
				returnValue += dataSet[dataSetIndex].registers[registerIndex+nextAddress] << 16
				returnValue *= self.multiplier

		if type(returnValue) == float:
			returnValue = round(returnValue, 2)
		return returnValue

	# Return True if data has been published and False otherwise
	def publishDataToMQTT(self):
		returnValue = False		
		registerData = self.getData()
		#print(self.registerName)
		#print(registerData)
		if registerData != "NotValid":
			#print("El valor es válido")
			try:
				# PEPE. Vo por aquí. Si registerData es un array de más de un elemento, el primero es el valory el resto van al topic /attributes
				#if self.baseAddress == 248:
				#	print("Attributes")
			
				publish.single(topic=MQTTTOPIC+self.registerName.lower(), payload=registerData, hostname=MQTTBROKER,
							   port=MQTTPORT, client_id=MQTTCLIENTID)#, auth = {'username':MQTTUSER, 'password':MQTTPASSW})
				#print("Dumped to mqtt")
				returnValue = True
			except:
				print("Error publishing to MQTT broker")
				
		#else:
		#	print("El valor no es válido")



class inverterData:
	# Name, First Address, Size in 16bit words, multiplier, unit
	RunningState				=	Register("RunningState", 59, 1, 1, "")
	DayActivePower				=	Register("DayActivePower", 60, 1, 0.1, "kWh")
	TotalActivePower			=	Register("TotalActivePower", 63, 2, 0.1, "kWh")
	DayBattCharge				=	Register("DayBattCharge", 70, 1, 0.1, "kwh")
	DayBattDischarge			=	Register("DayBattDisCharge", 71, 1, 0.1, "kwh")
	TotalBatteryChargePower		=	Register("TotalBatteryChargePower", 72, 2, 0.1, "W")
	TotalBatteryDischargePower	=	Register("TotalBatteryDischargePower", 74, 2, 0.1, "W")
	DayGridBuyPower				=	Register("DayGridBuyPower", 76, 1, 0.1, "kWh")
	DayGridSellPower			=	Register("DayGridSellPower", 77, 1, 0.1, "kWh")
	TotalGridBuyPower			=	Register("TotalGridBuyPower", 78, 2, 0.1, "kWh")		# Registers 78 and 80 instead of 78 and 79
	TotalGridSellPower			=	Register("TotalGridSellPower", 81, 2, 0.1, "kWh")
	DayLoadPower				=	Register("DayLoadPower", 84, 1, 0.1, "kWh")
	TotalLoadPower				=	Register("TotalLoadPower", 85, 2, 0.1, "kWh")
	YearLoadPower				=	Register("YearLoadPower", 87, 2, 0.1, "kWh")
	RadiatorTempDC				=	Register("RadiatorTempDC", 90, 1, 0.1, "ºC")
	IGBTTemp					=	Register("IGBTTemp", 91, 1, 0.1, "ºC")
	Inductance1Temp				=	Register("Inductance1Temp", 92, 1, 0.1, "ºC")
	EnvironmentTemp				=	Register("EnvironmentTemp", 95, 1, 0.1, "ºC")
	HistPVPower					=	Register("HistPVPower", 96, 2, 0.1, "kWh")
	DayPVPower					=	Register("DayPVPower", 108, 1, 0.1, "kWh")
	DCVoltage1					=	Register("DCVoltage1", 109, 1, 0.1, "V")
	DCCurrent1					=	Register("DCCurrent1", 110, 1, 0.1, "A")
	DCVoltage2					=	Register("DCVoltage2", 111, 1, 0.1, "V")
	DCCurrent2					=	Register("DCCurrent2", 112, 1, 0.1, "A")
	GridSideVoltageL1N			=	Register("GridSideVoltageL1N", 150, 1, 0.1, "V")
	LoadVoltageL1				=	Register("LoadVoltageL1", 157, 1, 0.1, "V")
	GridExternalTotalPower		=	Register("GridExternalTotalPower", 172, 1, 1, "W")
	LoadSideTotalPower			=	Register("LoadSideTotalPower", 178, 1, 1, "W")
	BatteryTemperature			=	Register("BatteryTemperature", 182, 1, 0.1, "ºC")
	BatteryVoltage				=	Register("BatteryVoltage", 183, 1, 0.01, "V")
	BatteryCapacity				=	Register("BatteryCapacity", 184, 1, 1, "%")
	PV1InputPower				=	Register("PV1InputPower", 186, 1, 1, "W")
	PV2InputPower				=	Register("PV2InputPower", 187, 1, 1, "W")
	BatteryOutputPower			=	Register("BatteryOutputPower", 190, 1, 1, "w")
	BatteryOutputCurrent		=	Register("BatteryOutputCurrent", 191, 1, 0.01, "A")
	GridSideRelayStatus			=	Register("GridSideRelayStatus", 194, 1, 1, "")			# 0=Disconnected ; 1=Connected
	TimeOfUseSelling			=	Register("TimeOfUSeSelling", 248, 1, 1, "")
	GridMode					=	Register("GridMode", 284, 1, 1, "")



#
# Read all inverter data in blocks
#
# returns:
#		 0 = All Registers
#		 1 = Some registers not readed
#		-1 = No register could be read
#

def readInverterData():
	global dataSet
	global inverterConnection
	#global dataSet2
	returnValue = -1
	dataSet1Readed = False
	dataSet2Readed = False

	#print(inverterConnection.is_socket_open())

	try:
		# Am I already connected
		if inverterConnection.is_socket_open() == False:
		#	print("Conectando al Inversor")
			inverterConnection.connect()  # Trying for connect to Modbus Server/Slave
		#else:
		#	print("Ya estoy connectado al inversor")

		if inverterConnection.is_socket_open():
			dataSet[0] = inverterConnection.read_holding_registers(address=dataSet1From, count=dataSet1Size, unit=1)
			if not dataSet[0].isError():
				#print("Primer lote leído.")
				dataSet1Readed = True
			else:
				dataSet1Readed = False

			dataSet[1] = inverterConnection.read_holding_registers(address=dataSet2From, count=dataSet2Size, unit=1)
			if not dataSet[1].isError():
				#print("Segundo lote leído.")
				dataSet2Readed = True
			else:
				dataSet2Readed = False

			if dataSet1Readed == True or dataSet2Readed == True:
				returnValue = 0
			else:
				returnValue = 1

			#inverterConnection.close()

		else:
			print('Cannot create modbus connection')
			returnValue = -1

	except IOError:
		print("Error reading from the inverter")
	except ValueError:
		print("Inverter response is invalid")
	except:
		print("An exception ocurred")
	
	return returnValue


#
# Code Starts here
#

try:
	continueReading = True
	dataPublisedCounter = 0
	while continueReading:
		tiempo = time.time()*1000

		# Connect and get data from the inverter
		dataReadResult = readInverterData()


		# Publish data
		# High rate data
		#print("Dump High Rate Data")

		inverterData.RunningState.publishDataToMQTT()
		inverterData.GridSideRelayStatus.publishDataToMQTT()
		PV1Power = inverterData.PV1InputPower.getData()
		PV2Power = inverterData.PV2InputPower.getData()
		if(PV1Power != "NotValid" and PV2Power != "NotValid"):
			print("Total PV Power ", PV1Power + PV2Power)

		inverterData.PV1InputPower.publishDataToMQTT()
		inverterData.PV2InputPower.publishDataToMQTT()

		inverterData.DCVoltage1.publishDataToMQTT()
		inverterData.DCCurrent1.publishDataToMQTT()
		inverterData.DCVoltage2.publishDataToMQTT()
		inverterData.DCCurrent2.publishDataToMQTT()
		inverterData.BatteryOutputPower.publishDataToMQTT()
		inverterData.BatteryOutputCurrent.publishDataToMQTT()
		inverterData.GridExternalTotalPower.publishDataToMQTT()
		inverterData.LoadSideTotalPower.publishDataToMQTT()

		# Publish low rate data
		if dataPublisedCounter % lowRateDataEvery == 0:

			#print("Dump Low Rate Data")

			# Home Assistant Energy panel data
			#print("Total Grid Sell", inverterData.TotalGridSellPower.getData())
			inverterData.TotalGridSellPower.publishDataToMQTT()
			#print("Total Grid Buy", inverterData.TotalGridBuyPower.getData())
			inverterData.TotalGridBuyPower.publishDataToMQTT()
			#print("Hist PV Power", inverterData.HistPVPower.getData())
			inverterData.HistPVPower.publishDataToMQTT()
			#print("Total Battery Charge Power", inverterData.TotalBatteryChargePower.getData())
			inverterData.TotalBatteryChargePower.publishDataToMQTT()
			#print("Total Battery Discharge Power", inverterData.TotalBatteryDischargePower.getData())
			inverterData.TotalBatteryDischargePower.publishDataToMQTT()

			inverterData.DayActivePower.publishDataToMQTT()
			inverterData.TotalActivePower.publishDataToMQTT()
			inverterData.DayBattCharge.publishDataToMQTT()
			inverterData.DayBattDischarge.publishDataToMQTT()
			inverterData.DayGridBuyPower.publishDataToMQTT()
			inverterData.DayGridSellPower.publishDataToMQTT()
			inverterData.DayLoadPower.publishDataToMQTT()
			inverterData.DayPVPower.publishDataToMQTT()
			inverterData.TotalLoadPower.publishDataToMQTT()
			inverterData.YearLoadPower.publishDataToMQTT()
			inverterData.TimeOfUseSelling.publishDataToMQTT()
			inverterData.GridMode.publishDataToMQTT()
			inverterData.RadiatorTempDC.publishDataToMQTT()
			inverterData.IGBTTemp.publishDataToMQTT()
			inverterData.Inductance1Temp.publishDataToMQTT()
			inverterData.EnvironmentTemp.publishDataToMQTT()
			inverterData.GridSideVoltageL1N.publishDataToMQTT()
			inverterData.LoadVoltageL1.publishDataToMQTT()
			inverterData.BatteryTemperature.publishDataToMQTT()
			inverterData.BatteryVoltage.publishDataToMQTT()
			inverterData.BatteryCapacity.publishDataToMQTT()


		print("")

		print(round(time.time()*1000-tiempo));

		if not loopMode:
			continueReading = False
		else:
			time.sleep(highRateDataDelay)
			# To avoid lack of data, retry this iteration if some error ocurred getting data from the inverter.
			if( not dataSet[0].isError() and not dataSet[1].isError()):
				dataPublisedCounter += 1

# If Control+C is pressed 
except KeyboardInterrupt:
	if inverterConnection.is_socket_open():
		inverterConnection.close()

	sys.exit()



