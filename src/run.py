import logging
import mqtt
import argparse
import yaml
import sawnee
import repeat
import datetime
import json
import requests
import time
import datetime
import calendar

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

parser = argparse.ArgumentParser(prog="Sawnee", description="Read yearly Sawnee EMC electricity totals")
parser.add_argument("--config", required=True, help="location of the config file")
parser.add_argument("--file", required=True, help="file to save to")
args = parser.parse_args()

with open(args.config, "r") as file:
	try:
		config_file = yaml.safe_load(file)
	except yaml.YAMLError as ex:
		logging.error("Invalid config file")
		print(ex)
		exit(1)

config = mqtt.create_config(config_file)
sawnee_config = sawnee.create_config(config_file)

def write_value(values):
    with open(args.file, "r") as file:
        try:
            value_file = yaml.safe_load(file)
        except yaml.YAMLError as ex:
            logging.error("Invalid value file")
            print(ex)
            exit(1)

    for key, value in values.items():
        if (value_file.get(key) is not None and value_file[key] > value):
            raise Exception(f"Value in file {value_file[key]} for {key} is larger than retrieved value {value}")
        if (value_file.get(key) is None or value_file[key] != value):
            logging.info(f"Replacing value for {key} in file {value_file.get(key)} with {value}")
            value_file[key] = value
    
    with open(args.file, 'w') as file:
        yaml.dump(value_file, file)
    
    total = 0
    for value in value_file.values():
        total += value
    return total

def fetch_value():
    session = requests.Session()
    try:
        logging.info("Logging in")
        login = session.post("https://sawnee.smarthub.coop/services/oauth/auth/v2", data={
            "userId": sawnee_config.username, 
            "password": sawnee_config.password,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0"
        })
        if login.status_code != 200:
            logging.error(f"Login failed with {login.status_code}")
            return None
        
        login_json = login.json()
        status = login_json.get("status")
        if status != "SUCCESS":
            logging.error(f"Login failed with {status}")
            return None
        
        auth = login_json.get("authorizationToken")
        if (auth is None):
            logging.error(f"No auth token")
            return None
        
        logging.info("Logged in")

        to_dt = datetime.datetime.fromtimestamp(int(time.time()))
        to_ux = calendar.timegm(to_dt.timetuple()) * 1000
        year = to_dt.year
        month = to_dt.month
        if month - 3 < 1:
            year = year - 1
            month = 12 - -(month - 3)
        else:
            month = month - 3
        from_dt = to_dt.replace(second=0, minute=0, hour=0, day=1, month=month, year=year)
        from_ux = calendar.timegm(from_dt.timetuple()) * 1000
        logging.info(f"Fetching data from {from_dt} to {to_dt}")

        data = session.post("https://sawnee.smarthub.coop/services/secured/utility-usage", json={
            "userId": sawnee_config.username,
            "accountNumber": sawnee_config.account_number,
            "serviceLocationNumber": sawnee_config.service_location_number,
            "endDateTime": to_ux,
            "startDateTime": from_ux,
            "includeDemand": False,
            "industries": ["ELECTRIC"],
            "screen": "USAGE_EXPLORER",
            "timeFrame": "DAILY"
        }, headers={
            "Authorization": f"Bearer {auth}",
            "Content-Type": "application/json",
            "CassandraCacheable": "USE_CACHE",
            "X-NISC-SMARTHUB-CUSTOMERNUMBER": None,
            "X-NISC-SMARTHUB-USERNAME": sawnee_config.username,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0"
        })

        if data.status_code != 200:
            logging.error(f"Data failed with {data.status_code}")
            return None
        
        chart_data = data.json().get("ELECTRIC")[0].get("meterToChartData")

        totals = {}
        for key in chart_data.keys():
            if key.__contains__(sawnee_config.service_location_number):
                meter_data = chart_data.get(key)
                for value in meter_data:
                    dt = datetime.datetime.fromtimestamp(int(value.get("x")) / 1000)
                    if dt >= from_dt:
                        key = f"{dt.year}-{dt.month}"
                        value = value.get("y")
                        if totals.get(key) is not None:
                            totals[key] = totals[key] + value
                        else:
                            totals[key] = value

        logging.info(f"Totals fetched from {from_dt} to {to_dt} is {totals}")
        return write_value(totals)
    except Exception as ex:
        logging.error(f"Error: {ex}")
        return None
    finally:
        logging.info("Closing connection")

def fetch_value_and_publish(client):
    logging.info(f"Refreshing")
    value = fetch_value()
    if value is None:
        logging.error("Nothing to publish")
    else:
        logging.info(f"Publishing {value} to [{config.topic}/{config.id}/status]")
        client.publish(f"{config.topic}/{config.id}/state", value, 2, True)

def publish_discovery(client):
    json_value = {
        "name": "Meter", 
        "state_topic": f"{config.topic}/{config.id}/state",
        "unique_id": f"{config.id}-sawnee",
        "device_class": "energy",
        "unit_of_measurement": "kWh",
        "state_class": "total_increasing",
        "device": {
            "name": config.topic.capitalize(),
            "manufacturer": config.topic.capitalize(),
            "model": config.topic.capitalize(),
            "ids": config.id
        }
    }
    logging.info(f"Publishing discovery to homeassistant/sensor/{config.topic}/{config.id}/config")
    client.publish(f"homeassistant/sensor/{config.topic}/{config.id}/config", json.dumps(json_value), 2, True)

repeating_timer = repeat.RepeatingTimer(sawnee_config.interval)

def on_connect(client, userdata, flags, rc):
    if (rc != 0):
        logging.error(f"MQTT connection failed with [{rc}]")
        exit(1)
    logging.info("MQTT connected")
    publish_discovery(client)
    logging.info(f"Subscribing to [{config.topic}/{config.id}/activate]")
    client.subscribe(f"{config.topic}/{config.id}/activate", 2)
    def callback():
        fetch_value_and_publish(client)
    repeating_timer.callback(callback)
    repeating_timer.start()
    
def on_disconnect(client, userdata, flags, rc):
    repeating_timer.callback(None)
    repeating_timer.stop()

def on_message(client, userdata, msg):
    handled = False
    if (msg.topic == f"{config.topic}/{config.id}/activate"):
        handled = True
        logging.info(f"Received refresh on [{config.topic}/{config.id}/activate]")
        fetch_value_and_publish(client)
    if not handled:
        logging.warning(f"MQTT message received but not recognized [{msg.topic}] [{msg.payload}]")

mqtt.run(config, on_connect, on_message, on_disconnect)