import logging
import publish

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

publish.publish("sawnee/activate")