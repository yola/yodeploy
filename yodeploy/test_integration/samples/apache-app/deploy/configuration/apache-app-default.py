from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'apache-app': {
            'domain': 'http://sampleservice.test',
            'cache': {
                'maxage': 60 * 60 * 60 * 24 * 365
            },
        },
        'foo': {
            'url': 'http://foo.site'
        },
    }
    return merge_dicts(config, new)
