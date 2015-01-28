from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'conftpl': {
            'secret': 'sauce',
            'msg': 'hi!',
        }
    }
    return merge_dicts(config, new)
