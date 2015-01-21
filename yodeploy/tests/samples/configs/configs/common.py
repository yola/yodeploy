import sys

from yoconfigurator.dicts import merge_dicts


def update(config):
    add = {
        'common': {
            'exampleservice': {
                'url': 'http://example.com/'
            },
        }
    }
    return merge_dicts(config, add)
