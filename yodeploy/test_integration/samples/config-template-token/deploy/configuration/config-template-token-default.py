from yoconfigurator.dicts import merge_dicts


def update(config):
    new = {
        'conftpl': {
            'secret': 'sauce',
            'msg': 'snowman!',
        }
    }
    return merge_dicts(config, new)
