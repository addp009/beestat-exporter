from flask import Flask, make_response

import os
import json
import urllib.request
import time
import gzip


app = Flask(__name__)


def convertToCelsius(fahrenheit):
    return (fahrenheit - 32) * 5.0 / 9.0


def generateBeestatThermostatMetrics(json_response):
    ecobeeThermostatId = list(json_response['data'].keys())
    
    prometheus_metrics = []

    # Adding header
    header = {
        "beestat_thermostat_connected_state": "# HELP beestat_thermostat_connected_state Ecobee connection status\n# TYPE beestat_thermostat_connected gauge",
        "beestat_thermostat_desired_cool_celsius": "# HELP beestat_thermostat_desired_cool_celsius Desired cooling temperature\n# TYPE beestat_thermostat_desired_cool gauge",
        "beestat_thermostat_desired_heat_celsius": "# HELP beestat_thermostat_desired_heat_celsius Desired heating temperature\n# TYPE beestat_thermostat_desired_heat gauge",
        "beestat_thermostat_actual_humidity_percent": "# HELP beestat_thermostat_actual_humidity_percent Actual humidity level\n# TYPE beestat_thermostat_actual_humidity gauge",
        "beestat_thermostat_desired_humidity_percent": "# HELP beestat_thermostat_desired_humidity_percent Desired humidity level\n# TYPE beestat_thermostat_desired_humidity gauge",
        "beestat_thermostat_actual_temperature_celsius": "# HELP beestat_thermostat_actual_temperature_celsius Actual temperature\n# TYPE beestat_thermostat_actual_temperature gauge",
    }

    for metricName in header:
        prometheus_metrics.append(header[metricName])

    for ecobeeThermostat in ecobeeThermostatId: 
        ecobee_name = json_response["data"][ecobeeThermostat]["name"]
        thermostat_firmware_version = json_response["data"][ecobeeThermostat]["version"]["thermostatFirmwareVersion"]

        metric_labels = 'ecobee_name="'+ ecobee_name + '",thermostat_firmware_version="' + thermostat_firmware_version + '"'

        runtime_metric_data = {
            "beestat_thermostat_connected_state": 1 if str(json_response["data"][ecobeeThermostat]["runtime"]["connected"]).lower() == "true" else 0,
            "beestat_thermostat_desired_cool_celsius": convertToCelsius(json_response["data"][ecobeeThermostat]["runtime"]["desiredCool"] / 10),
            "beestat_thermostat_desired_heat_celsius": convertToCelsius(json_response["data"][ecobeeThermostat]["runtime"]["desiredHeat"] / 10),
            "beestat_thermostat_actual_humidity_percent": json_response["data"][ecobeeThermostat]["runtime"]["actualHumidity"],
            "beestat_thermostat_desired_humidity_percent": json_response["data"][ecobeeThermostat]["extended_runtime"]["desiredHumidity"][-1],
            "beestat_thermostat_actual_temperature_celsius": convertToCelsius(json_response["data"][ecobeeThermostat]["runtime"]["actualTemperature"] / 10)
        }

        for key, value in runtime_metric_data.items():
            metric_line = f'{key}{{{metric_labels}}} {value}'
            prometheus_metrics.append(metric_line)
    
    return '\n'.join(prometheus_metrics)

def generateBeestatEquipmentState(json_response):
    ecobeeThermostatId = list(json_response['data'].keys())
    
    prometheus_metrics = []

    # Adding header
    header = '# HELP beestat_equipment_state Current status of equipment components\n' \
             '# TYPE beestat_equipment_state gauge'
    prometheus_metrics.append(header)

    for ecobeeThermostat in ecobeeThermostatId: 
        ecobeeName = json_response["data"][ecobeeThermostat]["name"]
        equipment_status = json_response["data"][ecobeeThermostat]["equipment_status"]

        equipment_status_dict = {
            "heatPump": "false",
            "heatPump2": "false",
            "heatPump3": "false",
            "compCool1": "false",
            "compCool2": "false",
            "auxHeat1": "false",
            "auxHeat2": "false",
            "auxHeat3": "false",
            "fan": "false",
            "humidifier": "false",
            "dehumidifier": "false",
            "ventilator": "false",
            "economizer": "false",
            "compHotWater": "false",
            "auxHotWater": "false"
        }

        for equipment in equipment_status:
            equipment_status_dict[equipment] = "true"
        
        for key, value in equipment_status_dict.items():
            metric_value = 1 if value == "true" else 0 
            prometheus_metrics.append(f'beestat_equipment_state{{ecobee_name="{ecobeeName}",equipment="{key}"}} {metric_value}')

    # Join the metrics into a single string 
    return '\n'.join(prometheus_metrics)

def generateBeestatRemoteSensorStatus(json_response):
    ecobeeThermostatId = list(json_response['data'].keys())

    prometheus_metrics = []

    header = '# HELP beestat_sensor_temperature_celsius Temperature from remote sensors (in Celsius)\n' \
            '# TYPE beestat_sensor_temperature_celsius gauge\n' \
            '# HELP beestat_sensor_humidity_percent Humidity from remote sensors\n' \
            '# TYPE beestat_sensor_humidity_percent gauge\n' \
            '# HELP beestat_sensor_occupancy_state Occupancy from remote sensors\n' \
            '# TYPE beestat_sensor_occupancy_state gauge'
    prometheus_metrics.append(header)

    for ecobeeThermostat in ecobeeThermostatId: 
        ecobeeName = json_response["data"][ecobeeThermostat]["name"]
        for sensor in json_response["data"][ecobeeThermostat]["remote_sensors"]:
            sensor_name = sensor["name"]
            
            for capability in sensor["capability"]:
                metric_type = capability["type"]
                metric_value = capability["value"]
                
                if metric_type == "temperature":
                    metric_value = convertToCelsius(float(metric_value) / 10)
                    metric_name = "beestat_sensor_temperature_celsius"
                elif metric_type == "humidity":
                    metric_name = "beestat_sensor_humidity_percent"
                elif metric_type == "occupancy":
                    metric_value = 1 if metric_value == "true" else 0
                    metric_name = "beestat_sensor_occupancy_state"
                
                metric = f'{metric_name}{{ecobee_name="{ecobeeName}",sensor_name="{sensor_name}"}} {metric_value}'
                prometheus_metrics.append(metric)

    # Join the metrics into a single string
    return '\n'.join(prometheus_metrics)

def generateBeestatEquipmentRuntimeMetrics(json_response):
    ecobeeThermostatId = list(json_response['data'].keys())

    prometheus_metrics = []

    header = '# HELP beestat_equipment_runtime_hours Accumulated equipment runtime.\n' \
            '# TYPE beestat_equipment_runtime_hours counter'
    prometheus_metrics.append(header)

    for ecobeeThermostat in ecobeeThermostatId: 
        ecobeeName = json_response["data"][ecobeeThermostat]["name"]    

        runtime_hour_data ={
            "cool_1": json_response["data"][ecobeeThermostat]["profile"]["runtime"]["cool_1"] / 60,
            "cool_2": json_response["data"][ecobeeThermostat]["profile"]["runtime"]["cool_2"] / 60,
            "heat_1": json_response["data"][ecobeeThermostat]["profile"]["runtime"]["heat_1"] / 60,
            "heat_2": json_response["data"][ecobeeThermostat]["profile"]["runtime"]["heat_2"] / 60,
            "auxiliary_heat_1": json_response["data"][ecobeeThermostat]["profile"]["runtime"]["auxiliary_heat_1"] / 60,
            "auxiliary_heat_2": json_response["data"][ecobeeThermostat]["profile"]["runtime"]["auxiliary_heat_2"] / 60,
            "furnace_filter": json_response["data"][ecobeeThermostat]["filters"]["furnace"]["runtime"] / 3600,
            "humidifier_filter": json_response["data"][ecobeeThermostat]["filters"]["humidifier"]["runtime"] / 3600,
        }

        for key, value in runtime_hour_data.items():
            metric_line = 'beestat_equipment_runtime_hours{ecobee_name="' + ecobeeName + '",equipment_name="' + key + '"} ' + str(value)
            prometheus_metrics.append(metric_line)

    return '\n'.join(prometheus_metrics)

def syncBeestatThermostat(apiKey):
    fetch_url="https://api.beestat.io/?api_key="+apiKey+"&resource=thermostat&method=sync"
    try:
        resp = urllib.request.urlopen(fetch_url)
    except Exception:
        print("Could not send GET request to given URL. Check url parameter!")
        exit(1)

    #check response code
    print(resp.code)
    if resp.code == "401":
        print("Invalid apiKey")
        exit(1)
    
    elif resp.code == 200:
        print("all right")
        # Successful call
    else:
        print("Web request returned unhandled HTTP status code " + str(resp.code) + ". Please open an issue at GitHub "                                                                               "with further details.")
        exit(1)

def decompressHttpContentEncoding(response):
    if response.getheader('Content-Encoding') == "gzip":
        data = gzip.decompress(response.read())
    else:
        data = response.read()
    
    return data



def generateBeestatMetrics():
    import json
    #check empty env vars
    if "BEESTAT_API_KEY" in os.environ:
        apiKey=os.environ["BEESTAT_API_KEY"]
    else:
        print("Set environment variable BEESTAT_API_KEY")
        exit(1)

    syncBeestatThermostat(apiKey)


    fetch_url="https://api.beestat.io/?api_key="+apiKey+"&resource=ecobee_thermostat&method=read_id"
    try:
        request = urllib.request.Request(fetch_url)
        request.add_header('Accept-Encoding', 'gzip')
        response = urllib.request.urlopen(request)
    except Exception:
        print("Could not send GET request to given URL. Check url parameter!")
        exit(1)

    print(response.code)
    if response.code != 200:
        print("Error calling beestat api. Status code != 200.")
        exit(1)

    ecobee_thermostat_payload = json.loads(decompressHttpContentEncoding(response).decode('utf-8'))

    if not ecobee_thermostat_payload["success"]:
        print("Error in response payload. `success != true`. ")
        exit(1)
    
    fetch_url="https://api.beestat.io/?api_key="+apiKey+"&resource=thermostat&method=read_id"
    try:
        request = urllib.request.Request(fetch_url)
        request.add_header('Accept-Encoding', 'gzip')
        response = urllib.request.urlopen(request)
    except Exception:
        print("Could not send GET request to given URL. Check url parameter!")
        exit(1)

    print(response.code)
    if response.code != 200:
        print("Error calling beestat api. Status code != 200.")
        exit(1)

    thermostat_payload = json.loads(decompressHttpContentEncoding(response).decode('utf-8'))

    if not thermostat_payload["success"]:
        print("Error in response payload. `success != true`. ")
        exit(1)

    prometheus_metrics_string = generateBeestatThermostatMetrics(ecobee_thermostat_payload)
    prometheus_metrics_string += "\n\n"
    prometheus_metrics_string += generateBeestatEquipmentState(ecobee_thermostat_payload)
    prometheus_metrics_string += "\n\n"
    prometheus_metrics_string += generateBeestatRemoteSensorStatus(ecobee_thermostat_payload)
    prometheus_metrics_string += "\n\n"
    prometheus_metrics_string += generateBeestatEquipmentRuntimeMetrics(thermostat_payload)

    # respons_txt = parsed_json
    return prometheus_metrics_string
    

@app.route('/metrics')
def metrics():
    response = make_response(generateBeestatMetrics(), 200)
    response.mimetype = "text/plain"
    return response



if "METRIC_PORT" in os.environ:
    SERVER_PORT=os.environ["METRIC_PORT"]
else:
    SERVER_PORT="9123"


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=SERVER_PORT)