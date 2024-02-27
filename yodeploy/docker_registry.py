import base64
import boto3
import json
import logging
import os
import subprocess
import yaml
from docker import APIClient

log = logging.getLogger(__name__)


class ECRClient:
    DOCKERFILES_DIR = os.path.join('deploy', 'docker')
    DOCKER_ENV_FILE = '/etc/yola/docker_apps.env'

    def __init__(self, aws_access_key_id, aws_secret_access_key,
                 ecr_registry_uri, ecr_registry_store,
                 aws_region='us-east-1',):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region
        self.ecr_registry_uri = ecr_registry_uri
        self.ecr_registry_store = ecr_registry_store

        # Initialize ECR client with explicit credentials
        self.ecr_client = boto3.client(
            'ecr',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
    def authenticate_docker_client(self):
        """
        Authenticates a Docker client using credentials obtained from the ECR client.

        Raises:
            Exception: If authentication fails or required configuration is missing.
        """

        if not self.ecr_registry_uri:
            raise Exception("Missing required configuration: 'ecr_registry_uri'")

        # Get ECR authorization token and extract username and password
        try:
            auth_token = self.ecr_client.get_authorization_token()
            token_data = base64.b64decode(auth_token['authorizationData'][0]['authorizationToken'])
            username, password = token_data.decode('utf-8').split(':')
        except Exception as e:
            self.logger.error(f"Failed to retrieve authentication token from ECR: {e}", exc_info=True)
            raise

        # Create Docker client and perform authentication
        try:
            self.docker_client = APIClient()
            self.docker_client.login(username=username, password=password, registry=self.ecr_registry_uri)
            self.logger.info(f"Successfully authenticated Docker client for ECR registry: {self.ecr_registry_uri}")
        except Exception as e:
            self.logger.error(f"Failed to authenticate Docker client: {e}", exc_info=True)
            raise

        return self.docker_client

    # def authenticate_docker_client(self):
        # Get token and Extract username and password
    #    auth_token = self.ecr_client.get_authorization_token()
    #    token_data = base64.b64decode(auth_token['authorizationData'][0]['authorizationToken'])
    #    username, password = token_data.decode('utf-8').split(':')

    #    self.docker_client = APIClient()
    #    self.docker_client.login(username=username, password=password, registry=self.ecr_registry_uri)

    #    return self.docker_client

    def create_ecr_repository(self, service_names, branch='master'):
        if not service_names:
            log.error("'service_names' are required.")
            return

        if branch not in ['master', 'release', 'docker']:
            log.info("Skipped ECR creation for branch '{}'.".format(branch))
            return

        for service_name in service_names:
            repository_name = "{}-{}".format(service_name.lower(), branch)

            try:
                response = self.ecr_client.create_repository(
                    repositoryName=repository_name,
                    imageScanningConfiguration={'scanOnPush': True},
                    imageTagMutability='IMMUTABLE'
                )
                repository_uri = response['repository']['repositoryUri']
                log.info("ECR Repo created: {}".format(repository_uri))

                # Add lifecycle policy to keep only last 5 images
                lifecycle_policy = {
                    'rules': [
                        {
                            'rulePriority': 1,
                            'description': 'Keep only last 5 images',
                            'selection': {
                                'tagStatus': 'any',
                                'countType': 'imageCountMoreThan',
                                'countNumber': 5,
                            },
                            'action': {'type': 'expire'}
                        }
                    ]
                }

                self.ecr_client.put_lifecycle_policy(
                    repositoryName=repository_name,
                    lifecyclePolicyText=json.dumps(lifecycle_policy)
                )

            except self.ecr_client.exceptions.RepositoryAlreadyExistsException:
                log.info("ECR Repo '{}' already exists.".format(repository_name))
            except Exception as e:
                log.error("An error occurred: {}".format(e), exc_info=True)

    def manipulate_docker_compose(self, image_uris):
        with open('compose.yaml', 'r') as file:
            compose_data = yaml.safe_load(file)

        for service_name, image_uri in image_uris.items():
            compose_data['services'][service_name]['image'] = image_uri

        with open('compose.yaml', 'w') as file:
            yaml.dump(compose_data, file, default_flow_style=False)

    def build_images(self, branch, version):
        service_names = self.get_apps_names()
        image_uris = self.construct_image_uris(self.ecr_registry_uri,
                                               service_names, branch, version)
        self.manipulate_docker_compose(image_uris)

        build_command = "{} build".format(self.docker_compose_command())

        try:
            subprocess.check_call(build_command, shell=True)
            log.info("Docker images built successfully")
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(e.returncode, e.cmd, e.output)

    def push_images(self, branch, version):
        if self.ecr_registry_store == 'local':
            log.info("Skipping push to AWS ECR (location set to 'local')")
            return

        self.authenticate_docker_client()
        service_names = self.get_apps_names()

        # Create ECR repository if it doesn't exist
        self.create_ecr_repository(service_names, branch)

        image_uris = self.construct_image_uris(self.ecr_registry_uri,
                                               service_names, branch, version)
        self.manipulate_docker_compose(image_uris)

        push_command = "{} push".format(self.docker_compose_command())

        try:
            subprocess.check_call(push_command, shell=True)
            log.info("Docker image pushed to AWS ECR successfully")
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(e.returncode, e.cmd, e.output)

    def docker_compose_command(self):
        return "docker compose --env-file {}".format(self.DOCKER_ENV_FILE)

    def get_apps_names(self, directory=None):
        """Retrieves application names from Dockerfiles within a directory,
          excluding tests images."""
        if directory is None:
            directory = os.getcwd()

        application = [
            os.path.splitext(dockerfile)[0]  # Remove ".Dockerfile" extension
            for dockerfile in os.listdir(directory)
            if dockerfile.endswith('.Dockerfile') and "tests" not in dockerfile
        ]
        return application

    def construct_image_uris(self, ecr_registry_uri,
                             service_names, branch, version):
        image_uris = {}
        for service_name in service_names:
            image_uri = "%s/%s-%s:%s" % (ecr_registry_uri,
                                         service_name, branch, version)
            image_uris[service_name] = image_uri
        return image_uris

    def pull_image(self, version, branch):
        if self.ecr_registry_store == 'local':
            log.info("Skipping pull from AWS ECR (location set to 'local')")
            return

        self.authenticate_docker_client()

        service_names = self.get_apps_names()
        image_uris = self.construct_image_uris(self.ecr_registry_uri,
                                               service_names, branch, version)
        self.manipulate_docker_compose(image_uris)

        pull_command = "{} pull".format(self.docker_compose_command())

        try:
            subprocess.check_call(pull_command, shell=True)
            log.info("Docker image pushed to AWS ECR successfully")
        except subprocess.CalledProcessError as e:
            log.error("Error pushing Docker image to AWS ECR: {}".format(e))
        log.info("Image pull complete for", image_uris)

    def cleanup_images(self, num_images_to_keep=5):
        self.authenticate_docker_client()

        images = self.docker_client.images()
        ecr_images = [
            img for img in images
            if any(self.ecr_registry_uri in t for t in img.get("RepoTags", []))
        ]
        dangling_images = [
            img for img in images
            if "<none>:<none>" in img.get("RepoTags", [])
        ]

        for img in dangling_images:
            img_id = img["Id"]
            self.docker_client.remove_image(img_id, force=True)

        sorted_images = sorted(
            ecr_images, key=lambda x: subprocess.check_output(
                ['docker', 'inspect', '-f',
                 '{{.Created}}', x['Id']]).decode('utf-8'))

        images_to_keep = sorted_images[-num_images_to_keep:]
        for img in sorted_images:
            if img not in images_to_keep:
                img_id = img["Id"]
                self.docker_client.remove_image(img_id, force=True)

        log.info("Removed obsolete images")
