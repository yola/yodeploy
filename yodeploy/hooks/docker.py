import subprocess
import logging

from yodeploy.hooks.base import DeployHook
from yodeploy.docker_registry import ECRClient


class DockerApp(DeployHook):
    def __init__(self, *args, **kwargs):
        super(DockerApp, self).__init__(*args, **kwargs)
        self.log = logging.getLogger(__name__)
        self.docker_base_dir = self.deploy_path('deploy', 'docker')
        self.docker_env_file = ECRClient.DOCKER_ENV_FILE

        self.ecr_client = ECRClient(
            aws_access_key_id=self.settings.artifacts.ecr_acccess_key,
            aws_secret_access_key=self.settings.artifacts.ecr_secret_key,
            aws_region='us-east-1',
            ecr_registry_uri=self.settings.artifacts.ecr_uri,
            ecr_registry_store=self.settings.artifacts.ecr_store
        )
        self.app_names = self.ecr_client.get_apps_names(self.docker_base_dir)

    def prepare(self):
        super(DockerApp, self).prepare()
        self.docker_prepare()

    def deployed(self):
        super(DockerApp, self).deployed()
        self.docker_deployed()

    def docker_compose_command(self):
        return "docker compose --env-file {}".format(self.docker_env_file)

    def start_container(self):
        command = self.docker_compose_command().split() + ['up', '-d']
        try:
            subprocess.check_call(
                command,
                cwd=self.docker_base_dir,
                shell=True,
            )
        except subprocess.CalledProcessError as e:
            self.log.error("Failed to start Docker container for {}: {}"
                           .format(self.app, str(e)))

    def docker_prepare(self):
        self.log.info("Pulling {} images with Docker...".format(self.app))
        self.ecr_client.pull_image(self.version, self.target)

    def docker_deployed(self):
        self.start_container()
        self.log.info("{} deployment completed.".format(self.app))
