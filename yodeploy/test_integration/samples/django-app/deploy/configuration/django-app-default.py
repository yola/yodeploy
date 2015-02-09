from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'django-app': {
            'domain': 'http://djangoapp.test',
            'environ': {
                'foo': 'bar'
            },
        },
    }
    return merge_dicts(config, new)
