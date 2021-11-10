import logging

def required_key(config_file_object, key):
    value = config_file_object.get(key)
    if (value is not None):
        return value
    else:
        logging.error(f"Key [{key}] is required on [{config_file_object}]")
        exit(1)