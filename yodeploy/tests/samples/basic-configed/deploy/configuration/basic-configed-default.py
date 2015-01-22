from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'basic-configed': {
            'secret': 'sauce',
        }
    }
    return merge_dicts(config, new)
