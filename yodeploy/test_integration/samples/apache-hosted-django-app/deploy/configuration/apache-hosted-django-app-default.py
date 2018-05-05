import os

from yoconfigurator.dicts import merge_dicts
from yodeploy.test_integration.helpers import tests_dir

log_dir = os.path.join(
    tests_dir, 'filesys', 'deployed', 'apache-hosted-django-app', 'logs'
)


def update(config):
    new = {
        'apache-hosted-django-app': {
            'domain': 'http://djangoapp.test',
            'environ': {
                'foo': 'bar'
            },
            'path': {
                'log': os.path.join(log_dir, 'app.log'),
                'celery_log': os.path.join(log_dir, 'app-celery.log'),
            }
        },
    }
    return merge_dicts(config, new)
