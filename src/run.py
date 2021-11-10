import logging
import mqtt
import argparse
import yaml
import sawnee
import repeat
import datetime
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions

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

def write_value(value):
    with open(args.file, "r") as file:
	    try:
		    value_file = yaml.safe_load(file)
	    except yaml.YAMLError as ex:
		    logging.error("Invalid value file")
		    print(ex)
		    exit(1)
    currentDateTime = datetime.datetime.now()
    date = currentDateTime.date()
    year = int(date.strftime("%Y"))
    logging.info
    if (value_file.get(year) is not None and value_file[year] > value):
        raise Exception(f"Value in file {value_file[year]} is larger than retrieved value {value}")
    if (value_file.get(year) is None or value_file[year] != value):
        logging.info(f"Replacing value in file {value_file.get(year)} with {value}")
        value_file[year] = value
        with open(args.file, 'w') as file:
            yaml.dump(value_file, file)
    total = 0
    for value in value_file.values():
        total += value
    return total

def fetch_value():
    logging.info("Opening connection")
    options = webdriver.FirefoxOptions()
    driver = webdriver.Remote(f"http://{sawnee_config.selenium}:4444", options=options)
    try:
        logging.info("Opening Sawnee")
        driver.get("https://sawnee.smarthub.coop/Login.html")
        logging.info("Entering username")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.ID, "LoginUsernameTextBox"))).send_keys(sawnee_config.username)
        logging.info("Entering password")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.ID, "LoginPasswordTextBox"))).send_keys(sawnee_config.password)
        logging.info("Submitting")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.ID, "LoginSubmitButton"))).click()
        logging.info("Clicking view usage")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.ID, "ViewUsageLink"))).click()
        logging.info("Clicking usage explorer")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, "//div[text()='Usage Explorer']"))).click()
        logging.info("Waiting for charts")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.CLASS_NAME, "highcharts-container")))
        logging.info("Clicking quick date control")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[@id='quickPicks']/*[@name='dateControl']"))).click()
        logging.info("Clicking year to date")
        year_to_date_button = None
        for button in driver.find_elements(By.CLASS_NAME, "btn-default"):
            if (button.text == "Year to Date"):
                year_to_date_button = button
        if year_to_date_button is None:
            raise Exception("Could not find year to date")
        year_to_date_button.click()
        logging.info("Waiting for charts")
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.CLASS_NAME, "highcharts-container")))
        logging.info("Finding total")
        value = int(driver.find_element(By.XPATH, "//table[@id='ce-alternateRowColor1']//tr[position()='6']/td[@align='right']/div").text.replace(",", ""))
        logging.info(f"Total {value}")
        return write_value(value)
    except Exception as ex:
        logging.error(f"Error: {ex}")
    finally:
        logging.info("Closing connection")
        driver.quit()

def fetch_value_and_publish(client):
    logging.info(f"Refreshing")
    value = fetch_value()
    logging.info(f"Publishing {value} to [{config.topic}/{config.id}/status]")
    client.publish(f"{config.topic}/{config.id}/state", value, 2, True)

def publish_discovery(client):
    json_value = {
        "name": config.topic.capitalize(), 
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