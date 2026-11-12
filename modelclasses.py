"""
# modelclasses.py
# Domain model class for tracking traveler satisfaction statistics and LED ring status
# Author: HectorAGonzalezFIU
"""

from Log import *
from Lights import GREEN, YELLOW, RED


class FeedbackStats:
    """
    Domain model class **FeedbackStats** that tracks positive and negative feedback
    counts, maintains the satisfaction score (0 to 100), and updates the 8-LED
    **LightStrip** indicator.

    Parameters:
    ----------
    lightstrip : LightStrip, optional
        Optional 8-LED NeoPixel LightStrip instance to update when score changes (default: None)

    Examples:
    ---------
    1. stats = FeedbackStats()
    2. stats.add_happy_count()
    3. stats.add_unhappy_count()
    4. stats.reset()
    """

    def __init__(self, lightstrip=None):
        """
        Initialize FeedbackStats with score = 100 and counts = 0.

        Parameters:
        ----------
        lightstrip : LightStrip, optional
            Optional LightStrip instance to update automatically (default: None)
        """
        Log.i("FeedbackStats: constructor")
        self._happy_count = 0
        self._unhappy_count = 0
        self._score = 100
        self._lightstrip = lightstrip
        self.update_lightstrip()

    def get_total_count(self) -> int:
        """
        Return the total number of feedback submissions (happy + unhappy).

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. total = stats.get_total_count()
        """
        total = self._happy_count + self._unhappy_count
        Log.i(f"FeedbackStats.get_total_count: {total}")
        return total

    def calculate_percentage(self) -> float:
        """
        Return the current satisfaction score percentage (0 to 100).

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. pct = stats.calculate_percentage()
        """
        Log.i(f"FeedbackStats.calculate_percentage: {self._score}%")
        return self._score

    def add_happy_count(self) -> None:
        """
        Record a positive (happy) feedback press: increments _happy_count by 1,
        adds 10 to _score (capped at 100), and updates the LED ring.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. stats.add_happy_count()
        """
        self._happy_count += 1
        self._score = min(100, self._score + 10)
        Log.i(
            f"FeedbackStats.add_happy_count: happy={self._happy_count}, score={self._score}%"
        )
        self.update_lightstrip()

    def add_unhappy_count(self) -> None:
        """
        Record a negative (unhappy) feedback press: increments _unhappy_count by 1,
        subtracts 10 from _score (minimum 0), and updates the LED ring.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. stats.add_unhappy_count()
        """
        self._unhappy_count += 1
        self._score = max(0, self._score - 10)
        Log.i(
            f"FeedbackStats.add_unhappy_count: unhappy={self._unhappy_count}, score={self._score}%"
        )
        self.update_lightstrip()

    def reset(self) -> None:
        """
        Reset the feedback counts to 0 and restore satisfaction score to 100.

        Parameters:
        ----------
        None

        Examples:
        ---------
        1. stats.reset()
        """
        self._happy_count = 0
        self._unhappy_count = 0
        self._score = 100
        Log.i("FeedbackStats.reset: stats reset to score=100%, counts=0")
        self.update_lightstrip()

    def update_lightstrip(self, lightstrip=None) -> None:
        """
        Update the 8-LED ring proportionally to _score using int(8 * (_score / 100.0)).
        Color is GREEN if > 5 LEDs, YELLOW if > 3 LEDs, and RED otherwise.
        Turns the strip off if num_leds <= 0.

        Parameters:
        ----------
        lightstrip : LightStrip, optional
            LightStrip instance to update if not already stored on self (default: None)

        Examples:
        ---------
        1. stats.update_lightstrip(my_lightstrip)
        """
        strip = lightstrip if lightstrip is not None else self._lightstrip
        if strip is None:
            return

        num_leds = int(8 * (self._score / 100.0))
        if num_leds <= 0:
            strip.off()
            Log.i(
                f"FeedbackStats.update_lightstrip: score={self._score}%, num_leds=0 (strip OFF)"
            )
            return

        if num_leds > 5:
            color = GREEN
        elif num_leds > 3:
            color = YELLOW
        else:
            color = RED

        strip.setColor(color, num_leds)
        Log.i(
            f"FeedbackStats.update_lightstrip: score={self._score}%, num_leds={num_leds}, color={color}"
        )

    def __str__(self) -> str:
        """
        Return a formatted string summary of the current satisfaction statistics.
        """
        return (
            f"Score: {self._score}% (Happy: {self._happy_count}, Unhappy: {self._unhappy_count})"
        )


if __name__ == "__main__":
    stats = FeedbackStats()
    Log.i(f"Initial: {stats}")
    assert stats.calculate_percentage() == 100
    assert stats.get_total_count() == 0

    stats.add_unhappy_count()
    stats.add_unhappy_count()
    assert stats.calculate_percentage() == 80
    assert stats.get_total_count() == 2

    stats.add_happy_count()
    assert stats.calculate_percentage() == 90
    assert stats.get_total_count() == 3

    stats.reset()
    assert stats.calculate_percentage() == 100
    assert stats.get_total_count() == 0

    Log.i("Testing complete - all FeedbackStats checks passed")
