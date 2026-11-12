"""
# main.py
# Main entry point for the LAX Airport Satisfaction Kiosk MicroPython application
# Author: HectorAGonzalezFIU
"""

from Log import *
from FeedbackController import FeedbackController


if __name__ == "__main__":
    Log.i("main: Initializing LAX Airport Satisfaction Kiosk")
    kiosk = FeedbackController()
    try:
        Log.i("main: Starting FeedbackController")
        kiosk.run()
    except KeyboardInterrupt:
        Log.i("main: Stopping FeedbackController")
        kiosk.stop()
