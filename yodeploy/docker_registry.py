import boto3
import base64
import json
import os
import logging
import subprocess
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
        # Get token and Extract username and password
        auth_token = self.ecr_client.get_authorization_token()
        token_data = base64.b64decode(auth_token['authorizationData']
                                      [0]['authorizationToken'])
        username, password = token_data.decode('utf-8').split(':')

        self.docker_client = APIClient()
        self.docker_client.login(username=username, password=password,
                                 registry=self.ecr_registry_uri)

    def create_ecr_repository(self, image_name, branch):
        if not image_name or not branch:
            log.error("Both 'image_name' and 'branch' are required.")
            return

        if branch not in ['master', 'release', 'docker']:
            log.info("Skipped ECR creation for branch '{}'".format(branch))
            return

        repository_name = "{}-{}".format(image_name.lower(), branch)

        try:
            response = self.ecr_client.create_repository(
                repositoryName=repository_name,
                imageScanningConfiguration={
                    'scanOnPush': True
                },
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
                        'action': {
                            'type': 'expire'
                        }
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

    def get_apps_names(self, dockerfiles_dir):
        """Retrieves application names from Dockerfiles within a directory,
          excluding tests images."""
        application_names = [
            os.path.splitext(dockerfile)[0]  # Remove ".Dockerfile" extension
            for dockerfile in os.listdir(dockerfiles_dir)
            if dockerfile.endswith('.Dockerfile') and "tests" not in dockerfile
        ]
        return application_names

    def _get_image_tag(self, dockerfile_name, version):
        """Helper method to create image name and tag."""
        image_name = dockerfile_name.replace('.Dockerfile', '')
        image_tag = "{}-{}".format(image_name, version)
        return image_name, image_tag

    def _get_ecr_repo_and_uri(self, image_name, branch, image_tag):
        """Helper method to calculate ECR repository name and image URI."""
        ecr_repo_name = "{}{}-{}".format(self.ecr_registry_uri, image_name, branch)
        ecr_image_uri = "{}:{}".format(ecr_repo_name, image_tag)
        return ecr_repo_name, ecr_image_uri

    def push_image(self, dockerfile_name, version, branch):
        if self.ecr_registry_store == 'local':
            log.info("Skipping push to AWS ECR (location set to 'local')")
            return

        self.authenticate_docker_client()

        image_name, image_tag = self._get_image_tag(dockerfile_name, version)
        ecr_repo_name, ecr_image_uri = self._get_ecr_repo_and_uri(image_name, branch, image_tag)

        # Create ECR repository if it doesn't exist
        self.create_ecr_repository(image_name, branch)

        # Show tagged images
        log.info("ECR Image URI:", ecr_image_uri)
        self.docker_client.tag(image="{}:{}".format(image_name, branch),
                               repository=ecr_repo_name,
                               tag=image_tag)

        # Push the image to ECR
        self.docker_client.push(repository=ecr_image_uri)
        log.info("Image push complete for:", ecr_image_uri)

    def pull_image(self, dockerfile_name, version, branch):
        if self.ecr_registry_store == 'local':
            log.info("Skipping pull from AWS ECR (location set to 'local')")
            return

        self.authenticate_docker_client()

        image_name, image_tag = self._get_image_tag(dockerfile_name, version)
        ecr_repo_name, ecr_image_uri = self._get_ecr_repo_and_uri(image_name, branch, image_tag)

        # Pull the image from ECR
        self.docker_client.pull(repository=ecr_repo_name, tag=image_tag)
        # Perform image cleanup after pulling
        self.cleanup_images()

        log.info("Image pull complete for:", ecr_image_uri)

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
