# -*- coding: utf-8 -*-
from yodeploy.hooks.configurator import ConfiguratedApp


class Hook(ConfiguratedApp):

    public_config_js_path = 'src/config.js'
    public_config_token = '☃☃☃'


hooks = Hook
