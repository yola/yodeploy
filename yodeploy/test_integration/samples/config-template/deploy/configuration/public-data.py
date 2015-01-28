from yoconfigurator.dicts import filter_dict


def filter(config):
    keys = [
        'conftpl.msg',
    ]
    return filter_dict(config, keys)
