import os.path
import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from ..util.ssh import sshmanager
from ..util.managedfile import ManagedFile



@attr.s(eq=False)
class BaseProviderDriver(Driver):
    @Driver.check_bound
    def get_export_vars(self):
        return {
            "host": self.provider.host,
            "internal": self.provider.internal,
            "external": self.provider.external,
        }

    @Driver.check_active
    @step(args=['filename'], result=True)
    def stage(self, filename):
        symlink = os.path.join(self.provider.internal, os.path.basename(filename))
        assert symlink.startswith(self.provider.internal)

        mf = ManagedFile(filename, self.provider)
        mf.sync_to_resource(symlink=symlink)

        return self.provider.external + symlink[len(self.provider.internal):]


@target_factory.reg_driver
@attr.s(eq=False)
class TFTPProviderDriver(BaseProviderDriver):
    bindings = {
        "provider": {"TFTPProvider", "RemoteTFTPProvider"},
    }

    @Driver.check_active
    @step(args=['filename'], result=True)
    def stage(self, filename):
        conn = sshmanager.open(self.provider.host)
        rpath = os.path.join(self.provider.internal, os.path.basename(filename))

        assert rpath.startswith(self.provider.internal)
        conn.run_check(f"mkdir -p {os.path.dirname(rpath)}")
        conn.put_file(filename, rpath)

        return self.provider.external + rpath[len(self.provider.internal):]


@attr.s
class NFSFile:
    host = attr.ib(validator=attr.validators.instance_of(str))
    export = attr.ib(validator=attr.validators.instance_of(str))
    relative_file_path = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_driver
@attr.s(eq=False)
class NFSProviderDriver(Driver):
    bindings = {
        "provider": {"NFSProvider", "RemoteNFSProvider"},
    }

    @Driver.check_bound
    def get_export_vars(self):
        return {
            "host": self.provider.host,
        }

    @Driver.check_active
    @step(args=['filename'], result=True)
    def stage(self, filename):
        # always copy the file to he user cache path:
        # locally available files might not be NFS-exported
        mf = ManagedFile(filename, self.provider, detect_nfs=False)
        mf.sync_to_resource()
        mf.get_remote_path()

        # assuming /var/cache/labgrid is NFS-exported, return required information for mounting and
        # file access
        relate_file_path = os.path.join(mf.get_hash(), os.path.basename(mf.local_path))
        return NFSFile(self.provider.host, mf.get_user_cache_path(), relate_file_path)


@target_factory.reg_driver
@attr.s(eq=False)
class HTTPProviderDriver(BaseProviderDriver):
    bindings = {
        "provider": {"HTTPProvider", "RemoteHTTPProvider"},
    }
