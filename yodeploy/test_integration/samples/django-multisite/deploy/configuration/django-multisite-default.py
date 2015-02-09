from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'django-multisite': {
            'domains': {
                'siteone': 'http://site-one.test',
                'sitetwo': 'http://site-two.test',
            },
            'environ': {
                'foo': 'bar'
            },
        },
    }
    return merge_dicts(config, new)
