from yodeploy.hooks.configurator import ConfiguratedApp


class Hook(ConfiguratedApp):

    public_config_path = 'src/config.js'


hooks = Hook
