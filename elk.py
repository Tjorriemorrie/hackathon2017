import click
from collections import namedtuple
from distutils.dir_util import 
import docker.errors
import json
import logging
import os.path
import ruamel.yaml
import time
import webbrowser

logger = logging.getLogger(__name__)


class DevElk:
    """Development ELK stack"""
    PWD = os.path.dirname(os.path.abspath(__file__))
    FILE_CONFIG = os.path.join(PWD, 'config.yaml')

    def __init__(self, host, remove):
        """setup arguments and connect"""
        with open(self.FILE_CONFIG, 'r') as f:
            self.config = ruamel.yaml.safe_load(f)
            logger.info('Loaded configuration')
        logger.info('{}'.format(json.dumps(self.config, indent=4, default=str)))

        self.config['host'] = host
        logger.info('host: {}'.format(self.config['host']))

        self.docker = docker.from_env()
        logger.info('connected to docker')

        self.network = None
        self.containers = {}
        self.pull_images = False

        logger.info('Removing containers on exit? {}'.format(remove))
        self.remove_containers = remove

    def run(self):
        """Run"""
        self.load_logs()
        self.start_network()
        self.start_containers()

        logger.info('Launching Kibana...')
        webbrowser.open('http://localhost:5601')

        logger.info('running')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info('shutting down gracefully...')
            self.stop_containers()

    def load_logs(self):
        """Load logs"""
        if self.host == 'localhost':


    def start_network(self):
        """Creates network"""
        logger.info('Creating network {}...'.format(self.config['network']['name']))
        self.docker.networks.prune()
        self.network = self.docker.networks.create(self.config['network']['name'])

    def start_containers(self):
        """Starts all containers"""
        for name, image in self.config['images'].items():
            logger.info('starting container {}'.format(name))

            logger.debug('docker images: {}'.format(self.docker.images.list()))
            if self.pull_images:
                logger.info('pulling {}...'.format(name))
                self.docker.images.pull(image['url'])

            logger.info('starting {}...'.format(name))
            try:
                con = self.docker.containers.get(image['name'])
            except docker.errors.NotFound:
                logger.debug('No existing {} container'.format(image['name']))
                volumes = {}
                if image['volumes']:
                    for d, binding in image['volumes'].items():
                        volumes[os.path.join(self.PWD, d)] = {
                            'bind': binding['bind'],
                            'mode': binding['mode']
                        }
                logger.debug('volumes: {}'.format(volumes))
                ports = {}
                if image['ports']:
                    ports = {i['int']: i['ext'] for i in image['ports']}
                logger.debug('ports: {}'.format(ports))
                con = self.docker.containers.run(
                    image['url'],
                    name=image['name'],
                    ports=ports,
                    environment=image['env'],
                    network_mode=self.network.name,
                    volumes=volumes,
                    detach=True)
            else:
                con.start()

            self.containers[name] = con
            logger.info('docker container {} running'.format(name))

            self.startup(con, image['startup'])

    def stop_containers(self):
        """Shuts down all containers
        Can remove containers as well"""
        for container in self.containers.values():
            logger.info('stopping {}...'.format(container.name))
            while True:
                try:
                    container.stop(timeout=5)
                    break
                except:
                    pass

            if self.remove_containers:
                logger.info('removing {}...'.format(container.name))
                container.remove()

    def startup(self, container, phrase):
        """Wait for a instance to startup"""
        logger.info('Waiting for {} to start...'.format(container.name))
        for log in container.logs(stream=True):
            logger.debug('log: {}'.format(log))
            if phrase in str(log):
                logger.info('Phrase found: {}'.format(phrase))
                break


@click.command()
@click.option('--host', type=click.STRING, default='localhost')
@click.option('--remove', is_flag=True)
def main(host, remove):
    DevElk(host, remove).run()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)-7s - %(name)-8s [%(funcName)s:%(lineno)d] :: %(message)s')
    main()
