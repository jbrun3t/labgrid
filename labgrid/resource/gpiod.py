import attr
import warnings

from ..factory import target_factory
from .common import Resource, NetworkResource
from .udev import USBResource

@target_factory.reg_resource
@attr.s(eq=False)
class GpiodGPIO(Resource):
    """The basic GpiodGPIO contains an device and an index

    Args:
        chip (str): gpio to connect to
        pin (int): index of target gpio line."""
    chip = attr.ib(default=None)
    pin = attr.ib(default=0, validator=attr.validators.instance_of(int))

@target_factory.reg_resource
@attr.s(eq=False)
class NetworkGpiodGPIO(NetworkResource):
    """The basic GpiodGPIO contains an device and an index

    Args:
        chip (str): gpio to connect to
        pin (int): index of target gpio line."""
    chip = attr.ib(default=None, validator=attr.validators.instance_of(str))
    pin = attr.ib(default=None, validator=attr.validators.instance_of(int))

@target_factory.reg_resource
@attr.s(eq=False)
class RawGpiodGPIO(GpiodGPIO, Resource):
    """RawSerialPort describes a Gpiod backed directly referenced by device name"""
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.chip is None:
            raise ValueError("RawGpiodGPIO must be configured with a Gpiod chip")

@target_factory.reg_resource
@attr.s(eq=False)
class USBGpiodGPIO(USBResource, GpiodGPIO):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'gpio'
        self.match['@SUBSYSTEM'] = 'usb'
        if self.chip:
            warnings.warn(
                "USBGpiodGPIO: The chip attribute will be overwritten by udev.\n"
                "Please use udev matching as described in http://labgrid.readthedocs.io/en/latest/configuration.html#udev-matching"  # pylint: disable=line-too-long
            )
        super().__attrs_post_init__()

    def filter_match(self, device):
        # Filter out the sysfs interface
        if device.properties.get('DEVNAME') is None:
            return False
        return super().filter_match(device)

    def update(self):
        super().update()
        if self.device is not None:
            self.chip = self.device.device_node
        else:
            self.chip = None
