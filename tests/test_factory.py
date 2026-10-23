from collections import OrderedDict
from copy import deepcopy

import attr
import pytest

from labgrid import Target, target_factory
from labgrid.driver import Driver
from labgrid.resource import Resource
from labgrid.exceptions import InvalidConfigError, RegistrationError
from labgrid.resource import SerialPort
from labgrid.util.yaml import load

def test_empty():
    t = target_factory.make_target('dummy', {})
    assert isinstance(t, Target)


def test_resources():
    original_config = {
        'resources': OrderedDict([
            ('RawSerialPort', {
                'port': 'foo',
                'speed': 115200,
                'name': 'console',
            }),
        ]),
    }
    config = deepcopy(original_config)
    t = target_factory.make_target('dummy', config)
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None
    assert config == original_config


def test_drivers():
    original_config = {
        'resources': OrderedDict([
            ('RawSerialPort', {
                'port': 'foo',
                'speed': 115200
            }),
        ]),
        'drivers': OrderedDict([
            ('FakeConsoleDriver', {
                'name': 'console',
            }),
            ('ShellDriver', {
                'name': 'shell',
                'prompt': '',
                'login_prompt': '',
                'username': ''
            }),
        ]),
    }
    config = deepcopy(original_config)
    t = target_factory.make_target('dummy', config)
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None
    assert config == original_config


def test_convert_dict():
    original_data = load("""
    FooPort: {}
    BarPort:
      name: bar
    """)
    data = deepcopy(original_data)
    l = target_factory._convert_to_named_list(data)
    assert l == [
        {
            'cls': 'FooPort',
            'name': None,
        },
        {
            'cls': 'BarPort',
            'name': 'bar'
        },
    ]
    assert data == original_data


def test_convert_simple_list():
    original_data = load("""
    - FooPort: {}
    - BarPort:
        name: bar
    """)
    data = deepcopy(original_data)
    l = target_factory._convert_to_named_list(data)
    assert l == [
        {
            'cls': 'FooPort',
            'name': None,
        },
        {
            'cls': 'BarPort',
            'name': 'bar'
        },
    ]
    assert data == original_data


def test_convert_explicit_list():
    original_data = load("""
    - cls: FooPort
    - cls: BarPort
      name: bar
    """)
    data = deepcopy(original_data)
    l = target_factory._convert_to_named_list(data)
    assert l == [
        {
            'cls': 'FooPort',
            'name': None,
        },
        {
            'cls': 'BarPort',
            'name': 'bar'
        },
    ]
    assert data == original_data


def test_normalize_config():
    original_config = {
        'resources': OrderedDict([
            ('RawSerialPort', {
                'port': 'foo',
                'speed': 115200
            }),
        ]),
        'drivers': OrderedDict([
            ('FakeConsoleDriver', {
                'name': 'console',
            }),
        ]),
    }
    config = deepcopy(original_config)
    resources, drivers = target_factory.normalize_config(config)

    assert 'RawSerialPort' in resources
    assert resources['RawSerialPort'] == {None: ({'port': 'foo', 'speed': 115200},)}

    assert 'FakeConsoleDriver' in drivers
    assert drivers['FakeConsoleDriver'] == {'console': ({}, {})}

    assert config == original_config


def test_convert_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - {}
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid empty dict as list item" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - "error"
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid list item type <class 'str'> (should be dict)" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - name: "bar"
          extra: "baz"
        """)
        target_factory._convert_to_named_list(data)
    assert "missing 'cls' key in OrderedDict(" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - one:
        - two: {}
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid list item, add empty dict for no arguments" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - one: "error"
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid arguments type <class 'str'> for one (should be dict)" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        one:
        two: {}
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid arguments for one, add empty dict for no arguments" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        one: "error"
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid arguments type <class 'str'> for one (should be dict)" in excinfo.value.msg


def test_resource_param_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_resource(
            None, 'NetworkSerialPort', 'serial', {'port': None})
    assert "failed to create" in excinfo.value.msg


def test_driver_param_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_driver(
            None, 'QEMUDriver', 'qemu', {'cpu': 'arm'})
    assert "failed to create" in excinfo.value.msg


def test_resource_class_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_resource(
            None, 'UnknownResource', None, {})
    assert "unknown resource class" in excinfo.value.msg


def test_driver_class_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_driver(
            None, 'UnknownDriver', None, {})
    assert "unknown driver class" in excinfo.value.msg


def test_register_same_driver():

    @attr.s
    class SameDriver(Driver):
        pass

    with pytest.raises(RegistrationError) as excinfo:
        target_factory.reg_driver(SameDriver)
        target_factory.reg_driver(SameDriver)
    assert "driver with name" in excinfo.value.msg

def test_register_same_resource():

    @attr.s
    class SameResource(Resource):
        pass

    with pytest.raises(RegistrationError) as excinfo:
        target_factory.reg_driver(SameResource)
        target_factory.reg_driver(SameResource)
    assert "driver with name" in excinfo.value.msg


def test_load_place_drivers():
    assert target_factory.load_place_drivers("") == []
    text = """
drivers:
  - ManualPowerDriver: {}
  - DigitalOutputPowerDriver:
      name: vbus
      bindings: {output: vbus}
"""
    assert target_factory.load_place_drivers(text) == [
        {'cls': 'ManualPowerDriver', 'name': None},
        {'cls': 'DigitalOutputPowerDriver', 'name': 'vbus', 'bindings': {'output': 'vbus'}},
    ]


@pytest.mark.parametrize("text,error", [
    ("foo: 1", "only a 'drivers' key"),
    ("- ManualPowerDriver: {}", "only a 'drivers' key"),
    ("drivers: {}\nfeatures: []", "only a 'drivers' key"),
    ("drivers: [}", "invalid YAML"),
    ("drivers:\n  - ManualPowerDriver: {name: !template '$LG_FOO'}", "cannot use template variables"),
    ("drivers:\n", "should be dict or list"),
])
def test_load_place_drivers_error(text, error):
    with pytest.raises(InvalidConfigError, match=error):
        target_factory.load_place_drivers(text)


PLACE_DRIVERS = {
    "board": """
drivers:
  - GpioDigitalOutputDriver:
      name: vbus
      bindings: {gpio: vbus}
  - DigitalOutputPowerDriver:
      name: vbus
      delay: 2.0
      bindings: {output: vbus}
""",
    "other": """
drivers:
  - DigitalOutputPowerDriver:
      name: vbus
""",
    "invalid": "resources: {}",
}


@pytest.fixture
def fake_places(monkeypatch):
    """Expand RemotePlace resources from PLACE_DRIVERS instead of a coordinator."""
    from labgrid.resource.common import ResourceManager
    from labgrid.resource.remote import RemotePlaceManager

    def on_resource_added(self, remote_place):
        new = target_factory.make_resource(remote_place.target, "SysfsGPIO", "vbus", {"index": 1})
        new.parent = remote_place
        remote_place.avail = True
        remote_place.drivers = PLACE_DRIVERS[remote_place.name]

    monkeypatch.setattr(ResourceManager, "instances", {})
    monkeypatch.setattr(RemotePlaceManager, "on_resource_added", on_resource_added)


def place_config(drivers=None, place="board"):
    config = {"resources": {"RemotePlace": {"name": place}}}
    if drivers is not None:
        config["drivers"] = drivers
    return config


def test_place_drivers(fake_places):
    t = target_factory.make_target("dummy", place_config([{"ManualPowerDriver": {"name": "manual"}}]))
    assert [(d.__class__.__name__, d.name) for d in t.drivers] == [
        ("GpioDigitalOutputDriver", "vbus"),
        ("DigitalOutputPowerDriver", "vbus"),
        ("ManualPowerDriver", "manual"),
    ]
    power = t.get_driver("DigitalOutputPowerDriver", activate=False)
    assert power.delay == 2.0
    assert power.output is t.get_driver("GpioDigitalOutputDriver", activate=False)


def test_place_drivers_replaced_in_position(fake_places):
    config = place_config([
        {"DigitalOutputPowerDriver": {"name": "vbus", "delay": 5.0, "bindings": {"output": "vbus"}}},
        {"GpioDigitalOutputDriver": {"name": "vbus", "bindings": {"gpio": "vbus"}}},
    ])
    t = target_factory.make_target("dummy", config)
    assert [(d.__class__.__name__, d.name) for d in t.drivers] == [
        ("GpioDigitalOutputDriver", "vbus"),
        ("DigitalOutputPowerDriver", "vbus"),
    ]
    assert t.get_driver("DigitalOutputPowerDriver", activate=False).delay == 5.0


def test_place_drivers_replaced_whole(fake_places):
    # the place's delay is not kept
    t = target_factory.make_target("dummy", place_config([{"DigitalOutputPowerDriver": {"name": "vbus"}}]))
    assert t.get_driver("DigitalOutputPowerDriver", activate=False).delay == 1.0


def test_place_drivers_disabled(fake_places):
    t = target_factory.make_target("dummy", place_config([{"ManualPowerDriver": {}}]), place_drivers=False)
    assert [d.__class__.__name__ for d in t.drivers] == ["ManualPowerDriver"]


def test_place_drivers_duplicate(fake_places):
    config = {"resources": [{"RemotePlace": {"name": "board"}}, {"RemotePlace": {"name": "other"}}]}
    with pytest.raises(InvalidConfigError, match="configured more than once"):
        target_factory.make_target("dummy", config)


def test_place_drivers_invalid(fake_places):
    with pytest.raises(InvalidConfigError, match="invalid drivers for place invalid"):
        target_factory.make_target("dummy", place_config(place="invalid"))
    target_factory.make_target("dummy", place_config(place="invalid"), place_drivers=False)
