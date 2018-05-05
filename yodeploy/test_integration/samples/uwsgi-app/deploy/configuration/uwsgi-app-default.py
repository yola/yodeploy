from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'uwsgi-app': {
            'uwsgi_specific_key': 'some_value',
        },
    }
    return merge_dicts(config, new)
