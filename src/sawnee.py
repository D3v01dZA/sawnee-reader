import util

class Config():
    def __init__(self, config_file):
        sawnee = util.required_key(config_file, "sawnee")
        self.username = util.required_key(sawnee, "username")
        self.password = util.required_key(sawnee, "password")
        self.account_number = util.required_key(sawnee, "account_number")
        self.service_location_number = util.required_key(sawnee, "service_location_number")
        self.interval = sawnee.get("interval", 60 * 15)

def create_config(config_file):
    return Config(config_file)
