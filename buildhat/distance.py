from .devices import PortDevice
from .exc import DeviceInvalid
from threading import Condition
import threading

class DistanceSensor(PortDevice):
    """Distance sensor

    :param port: Port of device
    :raises DeviceInvalid: Occurs if there is no distance sensor attached to port
    """
    def __init__(self, port, threshold_distance=100):
        super().__init__(port)
        if self._port.info()['type'] != 62:
            raise DeviceInvalid('There is not a distance sensor connected to port %s (Found %s)' % (port, self._whatami(port)))
        self._typeid = 62
        self._device.reverse()
        self._device.mode(0)
        self._callback = self.callback
        self._cond_data = Condition()
        self._when_in_range = None
        self._when_out_of_range = None
        self._fired_in = False
        self._fired_out = False
        self.threshold_distance = threshold_distance
        self._distance = -1

    def callback(self, data):
        self._distance = data[0]
        if self._when_in_range is not None:
            if self._distance != -1 and self._distance < self.threshold_distance and not self._fired_in:
                self._when_in_range()
                self._fired_in = True
                self._fired_out = False
        if self._when_out_of_range is not None:
            if self._distance != -1 and self._distance > self.threshold_distance and not self._fired_out:
                self._when_out_of_range()
                self._fired_in = False
                self._fired_out = True
        with self._cond_data:
            self._data = data[0]
            self._cond_data.notify()

    @property
    def distance(self):
        """
        :getter: Returns distance
        """
        return self._distance

    @property
    def threshold_distance(self):
        """
        :getter: Returns threshold distance
        :setter: Sets threshold distance
        """
        return self._threshold_distance

    @threshold_distance.setter
    def threshold_distance(self, value):
        self._threshold_distance = value

    def get_distance(self):
        """
        Returns the distance from ultrasonic sensor to object

        :return: Distance from ultrasonic sensor
        :rtype: int
        """
        dist = self._device.get(self._typeid)[0]
        return dist

    @property
    def when_in_range(self):
        """
        Handles motion events

        :getter: Returns function to be called when in range
        :setter: Sets function to be called when in range
        """
        return self._when_in_range

    @when_in_range.setter
    def when_in_range(self, value):
        """Calls back, when distance in range"""
        self._when_in_range = value
        self._device.callback(self._callback)

    @property
    def when_out_of_range(self):
        """
        Handles motion events

        :getter: Returns function to be called when out of range
        :setter: Sets function to be called when out of range
        """
        return self._when_out_of_range

    @when_out_of_range.setter
    def when_out_of_range(self, value):
        """Calls back, when distance out of range"""
        self._when_out_of_range = value
        self._device.callback(self._callback)

    def wait_for_out_of_range(self, distance):
        """Waits until distance is farther than specified distance

        :param distance: Distance
        """
        self._device.callback(self._callback)
        with self._cond_data:
            self._cond_data.wait()
            while self._data < distance:
                self._cond_data.wait()
        
    def wait_for_in_range(self, distance):
        """Waits until distance is closer than specified distance

        :param distance: Distance
        """
        self._device.callback(self._callback)
        with self._cond_data:
            self._cond_data.wait()
            while self._data > distance:
                self._cond_data.wait()
