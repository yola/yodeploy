from yola.deploy.hooks.python import PythonApp


class Hooks(PythonApp):
    def prepare(self):
        super(Hooks, self).prepare()

hooks = Hooks
