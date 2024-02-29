import logging

from yodeploy.hooks.base import DeployHook
from yodeploy.docker_registry import ECRClient


log = logging.getLogger(__name__)


class DockerApp(DeployHook):
    def __init__(self, *args, **kwargs):
        super(DockerApp, self).__init__(*args, **kwargs)

        self.ecr_client = ECRClient(
            aws_access_key_id=self.settings.artifacts.ecr_acccess_key,
            aws_secret_access_key=self.settings.artifacts.ecr_secret_key,
            aws_region='us-east-1',
            ecr_registry_uri=self.settings.artifacts.ecr_uri,
            ecr_registry_store=self.settings.artifacts.ecr_store
        )

    def prepare(self):
        super(DockerApp, self).prepare()
        self.docker_prepare()

    def deployed(self):
        super(DockerApp, self).deployed()
        self.docker_deployed()

    def docker_prepare(self):
        self.log.info("Pulling {} images with Docker...".format(self.app))
        self.ecr_client.pull_image(self.version, self.target)

    def docker_deployed(self):
        self.ecr_client.start_container()
        self.log.info("{} deployment completed.".format(self.app))
