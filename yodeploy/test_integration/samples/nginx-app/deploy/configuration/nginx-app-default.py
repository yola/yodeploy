from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'nginx-app': {
            'nginx_specific_key': 'some_value',
        },
    }
    return merge_dicts(config, new)
