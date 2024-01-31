"""All GPIOD-related drivers"""
from importlib import import_module
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class GpiodDigitalOutputDriver(Driver, DigitalOutputProtocol):

    bindings = {
        "res": {"GpiodGPIO", "NetworkGpiodGPIO"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('gpioset')
        else:
            self.tool = 'gpioset'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def _get_gpiod_cmd_prefix(self):
        return self.res.command_prefix + [ self.tool ]

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        args = [ '-t0', '-c', self.res.chip,
                 '{}={}'.format(self.res.pin,
                                1 if status == True else 0) ]
        processwrapper.check_output(self._get_gpiod_cmd_prefix() + args)

    @Driver.check_active
    @step(result=True)
    def get(self):
        self.logger.warning("\'get\' is not supported ATM")
        return False
