"""Test configuration file.

Settings file which specifies artifacts/ as a local store and srv/ as the apps
directory relative to whatever location this config file is placed at.

"""
import os

test_dir = os.path.dirname(__file__)


class AttrDict(dict):
    __getattr__ = dict.__getitem__

deploy_settings = AttrDict(
    artifacts=AttrDict(
        store='local',
        store_settings=AttrDict(
            local=AttrDict(
                directory=os.path.join(test_dir, 'artifacts'),
            ),
        ),
    ),
    paths=AttrDict(
        apps=os.path.join(test_dir, 'srv'),
    )
)
