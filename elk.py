import click
from collections import namedtuple
import docker.errors
import json
import logging
import os.path
import time
import webbrowser

logger = logging.getLogger(__name__)

ImageConfig = namedtuple('ImageConfig', ['name', 'url', 'ports', 'env', 'volumes'])


class DevElk:
    """Development ELK stack"""
    PWD = os.path.dirname(os.path.abspath(__file__))
    NETWORK = 'netelk'
    IMAGES = [
        ImageConfig(
            'develkes',
            'docker.elastic.co/elasticsearch/elasticsearch:5.4.0',
            ports={9200: 9200},
            env={
                'ES_JAVA_OPTS': '-Xms512m -Xmx512m',
                'xpack.security.enabled': 'false',
                'xpack.monitoring.enabled': 'false',
            },
            volumes={},
        ),
        ImageConfig(
            'develkls',
            'docker.elastic.co/logstash/logstash:5.4.0',
            ports={},
            env={
                'xpack.security.enabled': 'false',
                'xpack.monitoring.enabled': 'false',
            },
            volumes={
                '{}'.format(os.path.join(PWD, 'pipeline')): {
                    'bind': '/usr/share/logstash/pipeline', 'mode': 'ro'
                },
                '{}'.format(os.path.join(PWD, 'logs')): {
                    'bind': '/usr/share/logstash/logs', 'mode': 'ro'
                },
            },
        ),
        ImageConfig(
            'develkkb',
            'docker.elastic.co/kibana/kibana:5.4.0',
            ports={5601: 5601},
            env={
                'LOGGING_VERBOSE': True,
                'ELASTICSEARCH_URL': 'http://develkes:9200',
                'xpack.security.enabled': 'false',
                'xpack.monitoring.enabled': 'false',
            },
            volumes={},
        ),
    ]

    def __init__(self, host, remove):
        """setup arguments and connect"""
        self.host = host
        logger.info('host: {}'.format(self.host))

        self.client = docker.from_env()
        logger.info('connected to docker')

        self.network = None
        self.containers = {}
        self.pull_images = False

        logger.info('Removing containers on exit? {}'.format(remove))
        self.remove_containers = remove

    def run(self):
        """Run"""
        self.start_network()
        self.start_containers()
        self.launch()

        logger.info('running')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info('shutting down gracefully...')
            self.stop_containers()

    def start_network(self):
        """Creates network"""
        logger.info('Creating network {}...'.format(self.NETWORK))
        self.client.networks.prune()
        self.network = self.client.networks.create(self.NETWORK)

    def start_containers(self):
        """Starts all containers"""
        for image in self.IMAGES:
            logger.info('starting container {}'.format(image))

            logger.debug('docker images: {}'.format(self.client.images.list()))
            if self.pull_images:
                logger.info('pulling {}...'.format(image.name))
                self.client.images.pull(image.url)

            logger.info('starting {}...'.format(image.name))
            try:
                con = self.client.containers.get(image.name)
            except docker.errors.NotFound:
                logger.debug('No existing {} container'.format(image.name))
                # links = [(cn, cn) for cn in self.containers]
                con = self.client.containers.run(
                    image.url,
                    name=image.name,
                    ports=image.ports,
                    environment=image.env,
                    network_mode=self.network.name,
                    # links=links,
                    volumes=image.volumes,
                    detach=True)
            else:
                con.start()

            self.containers[image.name] = con
            logger.info('docker container {} running'.format(image.name))

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

    def launch(self):
        """Wait for a running kibanan instance to run and launch ui"""
        logger.info('Waiting for kibana to start...')
        con_kb = self.containers['develkkb']
        for log in con_kb.logs(stream=True):
            log = json.loads(log)
            logger.debug('kibana: {}'.format(log))
            if log['message'].startswith('Server running'):
                break
        logger.info('Launching Kibana...')
        webbrowser.open('http://localhost:5601')


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
