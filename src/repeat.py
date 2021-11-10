import logging
from threading import Thread
from threading import Event

class RepeatingTimer(Thread):
    def __init__(self, interval_seconds):
        super().__init__()
        self.stop_event = Event()
        self.interval_seconds = interval_seconds

    def callback(self, callback):
        self.callback = callback
        self.callback()

    def run(self):
        while not self.stop_event.wait(self.interval_seconds):
            if self.callback is not None:
                self.callback()

    def stop(self):
        self.stop_event.set()