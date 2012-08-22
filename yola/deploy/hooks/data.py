import logging
import os

from yola.deploy.util import chown_r
from .base import DeployHook

log = logging.getLogger(__name__)


class DataDirApp(DeployHook):
    def __init__(self, *args, **kwargs):
        super(DataDirApp, self).__init__(*args, **kwargs)

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

        data_dir = os.path.join(self.root, 'data')
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        chown_r(data_dir, 'www-data', 'www-data')

    def datadir_deployed(self):
        data_dir = os.path.join(self.root, 'data')
        if os.path.exists(data_dir):
            chown_r(data_dir, 'www-data', 'www-data')
