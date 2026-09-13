import threading


class Watchdog:
    def __init__(self, pump):
        self.pump = pump
        self.timer = None
        self.tripped = threading.Event()

    def arm(self, seconds):
        self.tripped.clear()

        def trip():
            self.tripped.set()
            self.pump.off()

        self.timer = threading.Timer(seconds, trip)
        self.timer.daemon = True
        self.timer.start()

    def disarm(self):
        self.pump.off()
        if self.timer:
            self.timer.cancel()
            self.timer.join(timeout=1)
        self.timer = None
