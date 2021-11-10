FROM ubuntu:20.04

# Setup timezone info
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Grab dependencies
RUN apt-get update && apt-get install -y python3 python3-pip
RUN pip3 install selenium
RUN pip3 install pyyaml
RUN pip3 install paho-mqtt

# Create the workspace
RUN mkdir -p /workspace
ADD ./src/. /workspace/

ENTRYPOINT [ "python3", "/workspace/run.py", "--config", "/data/config.yml",  "--file", "/data/file.yaml"]
