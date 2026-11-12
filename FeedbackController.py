"""
# FeedbackController.py
# StateModel controller for the LAX Airport Satisfaction Kiosk
# Author: HectorAGonzalezFIU
"""

import time
import utime
from Log import *
from StateModel import StateModel
from Counters import SoftwareTimer
from Displays import LCDDisplay
from LightStrip import LightStrip
from Lights import RED
from Buzzer import PassiveBuzzer, DO, MI, SO
from Button import Button
from modelclasses import FeedbackStats

try:
    from Sensors import UltrasonicSensor
except ImportError:
    from Sensors_advanced import UltrasonicSensor


class KioskSensor(UltrasonicSensor):
    """
    Subclass of **UltrasonicSensor** tailored for reliable Wokwi simulation.
    Uses a standard 10us trigger pulse in `distance()` and overrides `tripped()`
    to return `True` only when `0 < v <= self._threshold` (ignoring `-1` timeout
    readings).

    Parameters:
    ----------
    trigger : int
        GPIO pin number for the ultrasonic TRIG pin
    echo : int
        GPIO pin number for the ultrasonic ECHO pin
    name : str, optional
        Sensor name used for StateModel events (default: "us")
    lowActive : bool, optional
        True if sensor trips when distance is at or below threshold (default: True)
    threshold : float, optional
        Trip distance threshold in centimeters (default: 10.0)

    Examples:
    ---------
    1. sensor = KioskSensor(trigger=3, echo=4, name="us", threshold=10.0)
    2. is_close = sensor.tripped()
    """

    def distance(self) -> float:
        """
        Measure and return the distance in centimeters using a 10us trigger pulse.
        Returns -1 if the measurement times out.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. d = sensor.distance()
        """
        pulse_start = 0
        pulse_end = 0
        self._trigger.off()
        utime.sleep_us(2)
        self._trigger.on()
        utime.sleep_us(10)
        self._trigger.off()

        timeout = 30000  # 30ms timeout
        start = utime.ticks_us()
        while self._echo.value() == 0:
            if utime.ticks_diff(utime.ticks_us(), start) > timeout:
                return -1
            pulse_start = utime.ticks_us()

        start = utime.ticks_us()
        while self._echo.value() == 1:
            if utime.ticks_diff(utime.ticks_us(), start) > timeout:
                return -1
            pulse_end = utime.ticks_us()

        pulse_duration = utime.ticks_diff(pulse_end, pulse_start)
        distance_cm = (pulse_duration * 0.0343) / 2
        return round(distance_cm, 2)

    def tripped(self) -> bool:
        """
        Return True only when a valid positive distance reading is at or below
        the configured threshold (0 < v <= threshold), ignoring -1 timeouts.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. sensor.tripped()
        """
        v = self.rawValue()
        if v <= 0:
            return False

        if (self._lowActive and v <= self._threshold) or (
            not self._lowActive and v >= self._threshold
        ):
            Log.i(f"KioskSensor {self._name}: sensor tripped ({v} cm)")
            return True
        return False


class FeedbackController:
    """
    Controller class **FeedbackController** that coordinates the LAX Airport
    Satisfaction Kiosk using **StateModel** across 5 states (`0` to `4`).

    Parameters:
    ----------
    None

    Examples:
    ---------
    1. controller = FeedbackController()
    2. controller.run()
    """

    # State constants
    WELCOME = 0
    SELECTION = 1
    HAPPY = 2
    UNHAPPY = 3
    ALARM = 4

    def __init__(self):
        """
        Initialize all hardware peripherals, domain model (FeedbackStats),
        and the 5-state StateModel with its transitions.
        """
        Log.i("FeedbackController: constructor")

        # Step 1: Initialize hardware components matching Wokwi wiring
        # Red Button (Negative) = GP10, Green Button (Positive) = GP11
        self._display = LCDDisplay(sda=0, scl=1)
        self._lightstrip = LightStrip(pin=2, name="lightstrip", numleds=8, brightness=0.5)
        self._sensor = KioskSensor(
            trigger=3, echo=4, name="us", lowActive=True, threshold=10.0
        )
        self._red_button = Button(10, "red", handler=None)
        self._green_button = Button(11, "green", handler=None)
        self._buzzer = PassiveBuzzer(16, "buzzer")
        self._timer = SoftwareTimer(name="timer", handler=None)

        # Step 2: Initialize domain model
        self._stats = FeedbackStats(self._lightstrip)

        # Step 3: Initialize StateModel with 5 states (0 to 4)
        self._model = StateModel(5, self, debug=True)

        # Register buttons, sensor, timer, and custom event with StateModel
        self._model.addButton(self._green_button)
        self._model.addButton(self._red_button)
        self._model.addSensor(self._sensor)
        self._model.addTimer(self._timer)
        self._model.addCustomEvent("feedback_below_threshold")

        # Step 4: Add state transitions matching the Statechart diagram
        # State 0 (WELCOME) -> State 1 (SELECTION) on ultrasonic sensor trip
        self._model.addTransition(self.WELCOME, ["us_trip"], self.SELECTION)

        # State 1 (SELECTION) transitions
        self._model.addTransition(self.SELECTION, ["timer_timeout"], self.WELCOME)
        self._model.addTransition(self.SELECTION, ["green_press"], self.HAPPY)
        self._model.addTransition(self.SELECTION, ["red_press"], self.UNHAPPY)

        # State 2 (HAPPY) transitions (3s timeout back to WELCOME, or immediate button press)
        self._model.addTransition(self.HAPPY, ["timer_timeout"], self.WELCOME)
        self._model.addTransition(self.HAPPY, ["green_press"], self.HAPPY)
        self._model.addTransition(self.HAPPY, ["red_press"], self.UNHAPPY)

        # State 3 (UNHAPPY) -> State 4 (ALARM) if score < 30, 3s timeout to WELCOME, or immediate button press
        self._model.addTransition(
            self.UNHAPPY, ["feedback_below_threshold"], self.ALARM
        )
        self._model.addTransition(self.UNHAPPY, ["timer_timeout"], self.WELCOME)
        self._model.addTransition(self.UNHAPPY, ["green_press"], self.HAPPY)
        self._model.addTransition(self.UNHAPPY, ["red_press"], self.UNHAPPY)

        # State 4 (ALARM) -> State 0 (WELCOME) when manager presses green button
        self._model.addTransition(self.ALARM, ["green_press"], self.WELCOME)

    def _reset_sensor_state(self) -> None:
        """
        Reset the ultrasonic sensor's tracked status in StateModel._sensors back to
        (self._sensor, False) so that if the Wokwi distance slider remains at or below
        10cm, returning to WELCOME will cleanly detect the traveler and fire 'us_trip'
        on the next cycle.
        """
        for i, (sensor, status) in enumerate(self._model._sensors):
            if sensor == self._sensor:
                self._model._sensors[i] = (self._sensor, False)

    def stateEntered(self, state: int, event: str) -> None:
        """
        Perform entry actions when entering a state.

        Parameters:
        ----------
        state : int
            The state number being entered (0 to 4)
        event : str
            The event name that triggered the transition

        Examples:
        ---------
        1. controller.stateEntered(0, "no_event")
        """
        Log.d(f"State {state} entered on event {event}")

        if state == self.WELCOME:
            self._reset_sensor_state()
            self._display.reset()
            self._display.showText("Welcome to LAX", 0, 0)
            self._display.showText(f"Score: {self._stats.calculate_percentage()}%", 1, 0)
            self._stats.update_lightstrip(self._lightstrip)

        elif state == self.SELECTION:
            self._display.reset()
            self._display.showText("Welcome traveler", 0, 0)
            self._display.showText("How was visit?", 1, 0)
            self._timer.start(5)

        elif state == self.HAPPY:
            self._stats.add_happy_count()
            self._display.reset()
            self._display.showText("Thank you!", 0, 0)
            self._display.showText(f"Score: {self._stats.calculate_percentage()}%", 1, 0)
            self._buzzer.beep(tone=SO, duration=150)
            self._buzzer.beep(tone=MI, duration=150)
            self._timer.start(3)

        elif state == self.UNHAPPY:
            self._stats.add_unhappy_count()
            self._display.reset()
            self._display.showText("Sorry! Thank u", 0, 0)
            self._display.showText(f"Score: {self._stats.calculate_percentage()}%", 1, 0)
            self._buzzer.beep(tone=DO, duration=300)
            if self._stats.calculate_percentage() >= 30:
                self._timer.start(3)

        elif state == self.ALARM:
            self._display.reset()
            self._display.showText("Manager Called", 0, 0)
            self._display.showText("Green to reset", 1, 0)
            self._lightstrip.setColor(RED, 8)

    def stateLeft(self, state: int, event: str) -> None:
        """
        Perform exit actions when leaving a state.

        Parameters:
        ----------
        state : int
            The state number being exited (0 to 4)
        event : str
            The event name that triggered the transition

        Examples:
        ---------
        1. controller.stateLeft(1, "green_press")
        """
        Log.d(f"State {state} exited on event {event}")

        if state in (self.SELECTION, self.HAPPY, self.UNHAPPY):
            self._timer.cancel()
            if event == "timer_timeout":
                self._reset_sensor_state()

        elif state == self.ALARM:
            self._buzzer.stop()
            self._stats.reset()
            self._reset_sensor_state()

    def stateDo(self, state: int) -> None:
        """
        Perform continuous in-state activities for the active state.

        Parameters:
        ----------
        state : int
            The current active state number (0 to 4)

        Examples:
        ---------
        1. controller.stateDo(4)
        """
        if state == self.UNHAPPY:
            if self._stats.calculate_percentage() < 30:
                self._model.processEvent("feedback_below_threshold")

        elif state == self.ALARM:
            # Play a 2-tone alarm while in the ALARM state
            self._buzzer.beep(tone=800, duration=150)
            self._buzzer.beep(tone=400, duration=150)

    def stateEvent(self, state: int, event: str) -> bool:
        """
        Handle in-state events that do not cause a state transition.

        Parameters:
        ----------
        state : int
            The current active state number
        event : str
            The event name received

        Examples:
        ---------
        1. handled = controller.stateEvent(0, "green_press")
        """
        return False

    def run(self) -> None:
        """
        Start the StateModel event loop.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. controller.run()
        """
        Log.i("FeedbackController.run: starting state model")
        self._model.run(0.1)

    def stop(self) -> None:
        """
        Stop the StateModel and turn off hardware outputs.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. controller.stop()
        """
        Log.i("FeedbackController.stop: stopping state model")
        self._model.stop()
        self._buzzer.stop()
        self._lightstrip.off()
        self._display.reset()

    def __str__(self) -> str:
        """
        Return a string representation of the FeedbackController and its current state.
        """
        return f"FeedbackController(state={self._model._curState}, {self._stats})"


if __name__ == "__main__":
    controller = FeedbackController()
    Log.i(f"Initialized: {controller}")
    try:
        controller.run()
    except KeyboardInterrupt:
        controller.stop()
        Log.i("Testing complete - FeedbackController stopped cleanly")
