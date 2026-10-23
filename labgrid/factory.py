import inspect

from yaml import YAMLError

from .exceptions import InvalidConfigError, RegistrationError
from .util.dict import filter_dict
from .util.yaml import MergeMapping, load, resolve_templates


class TargetFactory:
    def __init__(self):
        self.resources = {}
        self.drivers = {}
        self.all_classes = {}

    def reg_resource(self, cls):
        """Register a resource with the factory.

        Returns the class to allow using it as a decorator."""
        cls_name = cls.__name__
        if cls_name in self.all_classes:
            raise RegistrationError(f"resource with name {cls_name} was already registered")
        self.resources[cls.__name__] = cls
        self._insert_into_all(cls)
        return cls

    def reg_driver(self, cls):
        """Register a driver with the factory.

        Returns the class to allow using it as a decorator."""
        cls_name = cls.__name__
        if cls_name in self.all_classes:
            raise RegistrationError(f"driver with name {cls_name} was already registered")
        self.drivers[cls_name] = cls
        self._insert_into_all(cls)
        return cls

    @staticmethod
    def _convert_to_named_list(data):
        """Convert a tree of resources or drivers to a named list.

        When using named resources or drivers, the config file uses a list of
        dicts instead of simply nested dicts. This allows creating multiple
        instances of the same class with different names.

        resources: # or drivers
          FooPort: {}
          BarPort:
            name: "bar"

        or

        resources: # or drivers
        - FooPort: {}
        - BarPort:
            name: "bar"

        should be transformed to

        resources: # or drivers
        - cls: "FooPort"
        - cls: "BarPort"
          name: "bar"
        """

        # resolve syntactic sugar (list of dicts each containing a dict of key -> args)
        result = []
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    raise InvalidConfigError(
                        f"invalid list item type {type(item)} (should be dict)")
                if not item:
                    raise InvalidConfigError("invalid empty dict as list item")
                if len(item) > 1:
                    if 'cls' in item:
                        item = item.copy()
                    else:
                        raise InvalidConfigError(f"missing 'cls' key in {item}")
                else:
                    # only one pair left
                    (key, value), = item.items()
                    if key == 'cls':
                        item = item.copy()
                    else:
                        item = MergeMapping(cls=key) if isinstance(value, MergeMapping) else {'cls':  key}
                        if value is None:
                            raise InvalidConfigError("invalid list item, add empty dict for no arguments")  # pylint: disable=line-too-long
                        if not isinstance(value, dict):
                            raise InvalidConfigError(
                                f"invalid arguments type {type(value)} for {key} (should be dict)")
                        item.update(value)
                result.append(item)
        elif isinstance(data, dict):
            for cls, args in data.items():
                if args is None:
                    raise InvalidConfigError(f"invalid arguments for {cls}, add empty dict for no arguments")
                if not isinstance(args, dict):
                    raise InvalidConfigError(f"invalid arguments type {type(args)} for {cls} (should be dict)")
                args = args.copy()
                args.setdefault('cls', cls)
                result.append(args)
        else:
            raise InvalidConfigError(f"invalid type {type(data)} (should be dict or list)")
        for item in result:
            item.setdefault('name', None)
            assert 'cls' in item
        return result

    @staticmethod
    def normalize_config(config):
        resources = {}
        drivers = {}
        for item in TargetFactory._convert_to_named_list(config.get('resources', {})):
            resource = item.pop('cls')
            name = item.pop('name', None)
            args = item # remaining args
            resources.setdefault(resource, {})[name] = (args, )
        for item in TargetFactory._convert_to_named_list(config.get('drivers', {})):
            driver = item.pop('cls')
            name = item.pop('name', None)
            bindings = item.pop('bindings', {})
            args = item # remaining args
            drivers.setdefault(driver, {})[name] = (args, bindings)
        return resources, drivers

    def make_resource(self, target, resource, name, args):
        assert isinstance(args, dict)
        if not resource in self.resources:
            raise InvalidConfigError(f"unknown resource class {resource}")
        try:
            cls = self.resources[resource]
            args = filter_dict(args, cls, warn=True)
            r = cls(target, name, **args)
        except TypeError as e:
            raise InvalidConfigError(
                f"failed to create {resource} for target '{target}' using {args} "
            ) from e
        return r

    def make_driver(self, target, driver, name, args):
        assert isinstance(args, dict)
        if not driver in self.drivers:
            raise InvalidConfigError(f"unknown driver class {driver}")
        try:
            cls = self.drivers[driver]
            args = filter_dict(args, cls, warn=True)
            d = cls(target, name, **args)
        except TypeError as e:
            raise InvalidConfigError(
                f"failed to create {driver} for target '{target}' using {args} ") from e
        return d

    @staticmethod
    def load_place_drivers(text):
        """Parse the driver configuration of a place.

        It describes how the place's resources are wired to the board (e.g. a GPIO switching
        its supply) as YAML with only a 'drivers' key, using the environment configuration
        syntax without template variables.

        Returns the drivers in the format of _convert_to_named_list().
        """
        if not text:
            return []
        try:
            data = load(text)
        except YAMLError as e:
            raise InvalidConfigError(f"invalid YAML: {e}") from e
        if not isinstance(data, dict) or set(data) != {'drivers'}:
            raise InvalidConfigError("must be a mapping with only a 'drivers' key")
        try:
            resolve_templates(data, {})
        except (KeyError, ValueError) as e:
            raise InvalidConfigError(f"cannot use template variables: {e}") from e
        drivers = TargetFactory._convert_to_named_list(data['drivers'])
        if any(isinstance(item, MergeMapping) for item in drivers):
            raise InvalidConfigError("cannot use !merge")
        return drivers

    @staticmethod
    def _get_place_drivers(target):
        """Return the drivers configured on the places of the target's RemotePlace resources."""
        from .resource.remote import RemotePlace

        drivers = []
        for resource in target.resources:
            if not isinstance(resource, RemotePlace):
                continue
            try:
                drivers.extend(TargetFactory.load_place_drivers(resource.drivers))
            except InvalidConfigError as e:
                raise InvalidConfigError(f"invalid drivers for place {resource.name}: {e}") from e
        return drivers

    @staticmethod
    def _merge_drivers(target, place_drivers, drivers):
        """Prepend the place drivers to the given driver list.

        A given driver with the same class and name as a place driver replaces it at the place
        driver's position, so that place drivers binding to it are still created after it.
        If the given driver is tagged with !merge, its arguments and bindings override those of
        the place driver instead, which must exist.
        """
        merged = []
        index = {}
        for item in place_drivers:
            key = (item['cls'], item['name'])
            if key in index:
                raise InvalidConfigError(
                    f"driver {item['cls']} named {item['name']} configured more than once by places of {target}"
                )
            index[key] = len(merged)
            merged.append(item)
        remaining = []
        for item in drivers:
            position = index.pop((item['cls'], item['name']), None)
            if isinstance(item, MergeMapping):
                if position is None:
                    raise InvalidConfigError(
                        f"no place driver {item['cls']} named {item['name']} to merge into in {target}"
                    )
                place_item = merged[position]
                bindings = {**place_item.get('bindings', {}), **item.get('bindings', {})}
                merged[position] = {**place_item, **item, 'bindings': bindings}
            elif position is None:
                remaining.append(item)
            else:
                merged[position] = item
        return merged + remaining

    def make_target(self, name, config, *, env=None, place_drivers=True):
        """Unless place_drivers is False, the drivers configured on the places of the target's
        RemotePlace resources are created as well, see _merge_drivers().
        """
        from .target import Target

        target = Target(name, env=env)
        for item in TargetFactory._convert_to_named_list(config.get('resources', {})):
            resource = item.pop('cls')
            name = item.pop('name', None)
            args = item # remaining args
            self.make_resource(target, resource, name, args)
        drivers = TargetFactory._convert_to_named_list(config.get('drivers', {}))
        place = TargetFactory._get_place_drivers(target) if place_drivers else []
        drivers = TargetFactory._merge_drivers(target, place, drivers)
        for item in drivers:
            driver = item.pop('cls')
            name = item.pop('name', None)
            bindings = item.pop('bindings', {})
            args = item # remaining args
            target.set_binding_map(bindings)
            self.make_driver(target, driver, name, args)
        return target

    def class_from_string(self, string: str):
        try:
            return self.all_classes[string]
        except KeyError:
            raise KeyError(f"No driver/resource/protocol of type '{string}' in factory, perhaps not registered?")

    def _insert_into_all(self, cls):
        classes = inspect.getmro(cls)
        for cl in classes:
            if not self.all_classes.get(cl.__name__):
                self.all_classes[cl.__name__] = cl


#: Global TargetFactory instance
#:
#: This instance is used to register Resource and Driver classes so that
#: Targets can be created automatically from YAML files.
target_factory = TargetFactory()
