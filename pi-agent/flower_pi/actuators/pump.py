"""Only the executor may command HIGH; emergency paths can only command LOW."""


class MockPump:
    def __init__(self):
        self.commanded_on = False
        self.starts = 0

    def _energize(self):
        self.commanded_on = True
        self.starts += 1

    def off(self):
        self.commanded_on = False


class GPIOPump:
    def __init__(self, pin=17):
        from gpiozero import OutputDevice

        self._output = OutputDevice(pin, active_high=True, initial_value=False)

    @property
    def commanded_on(self):
        return bool(self._output.value)

    def _energize(self):
        self._output.on()

    def off(self):
        self._output.off()
