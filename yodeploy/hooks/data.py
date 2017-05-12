import logging
import os

from yodeploy.hooks.base import DeployHook
from yodeploy.util import chown_r

log = logging.getLogger(__name__)


class DataDirApp(DeployHook):
    def prepare(self):
        super(DataDirApp, self).prepare()
        self.datadir_prepare()

    def deployed(self):
        super(DataDirApp, self).deployed()
        self.datadir_deployed()

    def datadir_prepare(self):
        log.debug('Running DataDirApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        chown_r(self.data_dir, 'www-data', 'www-data')

    def datadir_deployed(self):
        if os.path.exists(self.data_dir):
            chown_r(self.data_dir, 'www-data', 'www-data')

    @property
    def data_dir(self):
        return os.path.join(self.root, 'data')
