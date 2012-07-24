import imp

def load_settings(fn):
    '''Load deploy_settings from the specified filename'''
    fake_mod = '_deploy_settings'
    description = ('.py', 'r', imp.PY_SOURCE)
    with open(fn) as f:
        m = imp.load_module(fake_mod, f, fn, description)
    return m.deploy_settings
