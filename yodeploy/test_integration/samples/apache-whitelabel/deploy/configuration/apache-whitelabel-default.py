from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'apache-whitelabel': {
            'domain': {
                'yola': 'http://appname.yola',
                'wl': 'http://appname.wl',
            }
        }
    }
    return merge_dicts(config, new)
