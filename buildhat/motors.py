from .devices import PortDevice, Device
from .exc import DeviceInvalid
from threading import Condition
from collections import deque
from enum import Enum
import threading
import statistics

class Direction(Enum):
    CLOCKWISE = 0,
    ANTICLOCKWISE = 1,
    SHORTEST = 2

class Motor(PortDevice):
    """Motor device

    :param port: Port of device
    :raises DeviceInvalid: Occurs if there is no motor attached to port
    """
    # See hub-python-module/drivers/m_sched_shortcake.h
    MOTOR_SET = set([38, 46, 47, 48, 49, 65, 75, 76])

    def __init__(self, port):
        super().__init__(port)
        if self._port.info()['type'] not in Motor.MOTOR_SET:
            raise DeviceInvalid('There is not a motor connected to port %s (Found %s)' % (port, self._whatami(port)))
        self._motor = self._port.motor
        self.default_speed = 20
        self._device.mode([(1,0),(2,0),(3,0)])
        self._motor.plimit(0.7)
        self._motor.bias(0.3)
        self._release = True
        self._bqueue = deque(maxlen=5)
        self._cvqueue = Condition()
        self.when_rotated = None
        self._oldpos = None
        #self._motor.coast()

    def set_default_speed(self, default_speed):
        """Sets the default speed of the motor

        :param default_speed: Speed ranging from -100 to 100
        """
        if not (default_speed >= -100 and default_speed <= 100):
            raise MotorException("Invalid Speed")
        self.default_speed = default_speed

    def _isfinishedcb(self, speed, pos, apos):
        self._cvqueue.acquire()
        self._bqueue.append(pos)
        self._cvqueue.notify()
        self._cvqueue.release()

    def _blocktillfin(self):
        self._cvqueue.acquire()
        while True:
            self._cvqueue.wait()
            if len(self._bqueue) >= 5:
                dev = statistics.stdev(self._bqueue)
                if dev < 1:
                    self._motor.coast()
                    self._cvqueue.release()
                    return

    def run_for_rotations(self, rotations, speed=None, blocking=True):
        """Runs motor for N rotations

        :param rotations: Number of rotations
        :param speed: Speed ranging from -100 to 100
        """
        if speed is None:
            self.run_for_degrees(int(rotations * 360), self.default_speed, blocking)
        else:
            if not (speed >= -100 and speed <= 100):
                raise MotorException("Invalid Speed")
            self.run_for_degrees(int(rotations * 360), speed, blocking)

    def _run_for_degrees(self, newpos, origpos, speed):
        self._motor.run_for_degrees(newpos, origpos, speed)
        if self._release:
            self._blocktillfin()

    def run_for_degrees(self, degrees, speed=None, blocking=True):
        """Runs motor for N degrees

        :param degrees: Number of degrees to rotate
        :param speed: Speed ranging from -100 to 100
        """
        if speed is None:
            speed = self.default_speed
        if not (speed >= -100 and speed <= 100):
            raise MotorException("Invalid Speed")
        mul = 1
        if speed < 0:
            speed = abs(speed)
            mul = -1
        origpos = self.get_position()
        newpos = ((degrees*mul)+origpos)/360.0
        origpos /= 360.0
        if not blocking:
            th = threading.Thread(target=self._run_for_degrees, args=(newpos, origpos, speed))
            th.daemon = True
            th.start()
        else:
            self._run_for_degrees(newpos, origpos, speed)

    def run_to_position(self, degrees, speed=None, blocking=True):
        """Runs motor to position (in degrees)

        :param degrees: Position in degrees
        :param speed: Speed ranging from 0 to 100
        """
        if speed is None:
            speed = self.default_speed
        if not (speed >= 0 and speed <= 100):
            raise MotorException("Invalid Speed")
        pos = self.get_position()
        apos = self.get_aposition()
        newpos = (degrees-apos+pos)/360.0
        newpos = (pos + (degrees-apos+180) % 360 - 180)/360

        if not blocking:
            th = threading.Thread(target=self._run_for_degrees, args=(newpos, pos, speed))
            th.daemon = True
            th.start()
        else:
            self._run_for_degrees(newpos, pos, speed)

    def _run_for_seconds(self, seconds, speed):
        self._motor.run_for_time(seconds, speed, True)
        if self._release:
            self._motor.coast()

    def run_for_seconds(self, seconds, speed=None, blocking=True):
        """Runs motor for N seconds

        :param seconds: Time in seconds
        :param speed: Speed ranging from -100 to 100
        """
        if speed is None:
            speed = self.default_speed
        if not (speed >= -100 and speed <= 100):
            raise MotorException("Invalid Speed")
        if not blocking:
            th = threading.Thread(target=self._run_for_seconds, args=(seconds, speed))
            th.daemon = True
            th.start()
        else:
            self._run_for_seconds(seconds, speed)

    def start(self, speed=None):
        """Start motor

        :param speed: Speed ranging from -100 to 100
        """
        if speed is None:
            self._motor.run_at_speed(self.default_speed)
        else:
            if not (speed >= -100 and speed <= 100):
                raise MotorException("Invalid Speed")
            self._motor.run_at_speed(speed)

    def stop(self):
        """Stops motor"""
        self._motor.coast()

    def get_position(self):
        """Gets position of motor with relation to preset position (can be negative or positive).

        :return: Position of motor
        :rtype: int
        """
        return self._motor.get()[1]

    def get_aposition(self):
        """Gets absolute position of motor

        :return: Absolute position of motor
        :rtype: int
        """
        return self._motor.get()[2]

    def get_speed(self):
        """Gets speed of motor

        :return: Speed of motor
        :rtype: int
        """
        return self._motor.get()[0]

    @property
    def when_rotated(self):
        """
        Handles rotatation events

        :getter: Returns function to be called when rotated
        :setter: Sets function to be called when rotated
        """
        return self._when_rotated

    def _intermediate(self, value, speed, pos, apos):
        if self._oldpos is None:
            self._oldpos = pos
            return
        if abs(pos - self._oldpos) >= 1:
            value(speed, pos, apos)
            self._oldpos = pos

    @when_rotated.setter
    def when_rotated(self, value):
        """Calls back, when motor has been rotated"""
        if value is not None:
            self._when_rotated = lambda lst: [self._intermediate(value, lst[0], lst[1], lst[2]),self._isfinishedcb(lst[0], lst[1], lst[2])]
        else:
            self._when_rotated = lambda lst: self._isfinishedcb(lst[0], lst[1], lst[2])
        self._device.callback(self._when_rotated)


class MotorPair(Device):
    """Pair of motors

    :param motora: One of the motors to drive
    :param motorb: Other motor in pair to drive
    :raises RuntimeError: Occurs if there is no motor attached to port
    """
    def __init__(self, leftport, rightport):
        super().__init__()
        self._leftmotor = Motor(leftport)
        self._rightmotor = Motor(rightport)
        self.default_speed = 50

    def set_default_speed(self, default_speed):
        """Sets the default speed of the motor

        :param default_speed: Speed ranging from -100 to 100
        """
        self.default_speed = default_speed

    def run_for_rotations(self, rotations, speedl=None, speedr=None):
        """Runs pair of motors for N rotations

        :param rotations: Number of rotations
        :param speedl: Speed ranging from -100 to 100
        :param speedr: Speed ranging from -100 to 100
        """
        if speedl is None:
            speedl = self.default_speed
        if speedr is None:
            speedr = self.default_speed
        self._leftmotor.run_for_degrees(int(rotations * 360), speedl)
        self._rightmotor.run_for_degrees(int(rotations * 360), speedr)

    def run_for_degrees(self, degrees, speedl=None, speedr=None):
        """Runs pair of motors for degrees

        :param degrees: Number of degrees
        :param speedl: Speed ranging from -100 to 100
        :param speedr: Speed ranging from -100 to 100
        """
        if speedl is None:
            speedl = self.default_speed
        if speedr is None:
            speedr = self.default_speed
        self._leftmotor.run_for_degrees(degrees, speedl)
        self._rightmotor.run_for_degrees(degrees, speedr)

    def run_for_seconds(self, seconds, speedl=None, speedr=None):
        """Runs pair for N seconds

        :param seconds: Time in seconds
        :param speedl: Speed ranging from -100 to 100
        :param speedr: Speed ranging from -100 to 100
        """
        if speedl is None:
            speedl = self.default_speed
        if speedr is None:
            speedr = self.default_speed
        th1 = threading.Thread(target=self._leftmotor._run_for_seconds, args=(seconds,), kwargs={'speed': speedl, 'blocking': True})
        th1.daemon = True
        th2 = threading.Thread(target=self._rightmotor._run_for_seconds, args=(seconds,), kwargs={'speed': speedr, 'blocking': True})
        th2.daemon = True
        th1.start()
        th2.start()
        th1.join()
        th2.join()

    def start(self, speedl=None, speedr=None):
        """Start motors

        :param speed: Speed ranging from -100 to 100
        """
        if speedl is None:
            speedl = self.default_speed
        if speedr is None:
            speedr = self.default_speed
        self._leftmotor.start(speedl)
        self._rightmotor.start(speedr)

    def stop(self):
        """Stop motors"""
        self._leftmotor.stop()
        self._rightmotor.stop()

    def run_to_position(self, degreesl, degreesr, speed=None):
        """Runs pair to position (in degrees)

           :param degreesl: Position in degrees for left motor
           :param degreesr: Position in degrees for right motor
           :param speed: Speed ranging from -100 to 100
        """
        if speed is None:
            self._leftmotor.run_to_position(degreesl, self.default_speed)
            self._rightmotor.run_to_position(degreesr, self.default_speed)
        else:
            self._leftmotor.run_to_position(degreesl, speed)
            self._rightmotor.run_to_position(degreesr, speed)
