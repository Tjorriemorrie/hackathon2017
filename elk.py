import click
import coloredlogs
import datetime
from distutils.dir_util import copy_tree
import docker.errors
import json
import logging
import os.path
from pexpect import popen_spawn, EOF
import requests
import ruamel.yaml
import time
import webbrowser

logger = logging.getLogger(__name__)


class DevElk:
    """Development ELK stack"""
    PWD = os.path.dirname(os.path.abspath(__file__))
    FILE_CONFIG = os.path.join(PWD, 'config.yaml')
    remove_containers = False

    def __init__(self, host):
        """setup arguments and connect"""
        with open(self.FILE_CONFIG, 'r') as f:
            self.config = ruamel.yaml.safe_load(f)
            logger.info('Loaded configuration')
        logger.info('{}'.format(json.dumps(self.config, indent=4, default=str)))

        self.host = host
        logger.info('host: {}'.format(self.host))

        self.docker = docker.from_env()
        logger.info('connected to docker')

        self.network = None
        self.containers = {}
        self.pull_images = False

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
                self.get_server_log()
        except KeyboardInterrupt:
            logger.info('shutting down gracefully...')
            self.stop_containers()

    def load_logs(self):
        """Load logs"""
        self.clear_logs()
        if self.host == 'localhost':
            log_path = 'C:/{xplan_base}/var/{xplan_site}/log'.format(
                xplan_base=self.config['xplan_base'],
                xplan_site=self.config['xplan_site']
            )
            logger.info('Copying logs from localhost dir: {}'.format(log_path))
            copy_tree(log_path, os.path.join(self.PWD, 'logs'))
        else:
            self.compile_hotfix()
            self.get_server_log()

    def clear_logs(self):
        """Clear current log directory"""
        logger.info('clearing log directory...')
        for root, dirs, files in os.walk(os.path.join(self.PWD, 'logs'), topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
                logger.debug('removed {}'.format(name))

    def get_server_log(self):
        """Send hotfix to host and get log"""
        data = {
            'process': '__all__',
            'params': [],
        }
        files = {
            'hotfix': open('C:/xplanbase/version/hotfix/logfiles/get_serverlog.pys', 'rb')
        }
        res = requests.post('{}/hotfix'.format(self.host), data=data, files=files)
        res.raise_for_status()
        if 'gpg execution failed' in res.text:
            raise RuntimeError('Hotfix not signed')
        logger.info('response size: {}'.format(len(res.text)))
        tmp_logfile = os.path.join(self.PWD, 'logs', 'server.log')
        logger.debug('saving fetched log info to {}'.format(tmp_logfile))
        with open(tmp_logfile, 'wb') as f:
            f.write(res.text.encode('UTF-8'))
        logger.debug('log:\n{}'.format(res.text))
        0/0
        logger.info('res saved to file')

    def compile_hotfix(self):
        """Compiles hotfix"""
        logger.info('Compiling hotfix... not supported')
        return
        cmd = [
            # '"C:\cygwin64\bin\run.exe', '-p',
            'sh',
            'C:/xplanbase/version/hotfix/bin/compile_hotfix.sh',
            'C:/xplanbase/version/hotfix/logfiles/get_serverlog.py',
        ]
        logger.info('cmd = {}'.format(cmd))
        p = popen_spawn.PopenSpawn(cmd)
        logger.info(p.before)
        try:
            p.expect('Password:')
            p.sendline('foo')
        except EOF as e:
            logger.error(e)
            logger.info('before {}'.format(p.before))
            logger.info('after {}'.format(p.after))
        logger.info('Compiling hotfix done')

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
                        # volumes[os.path.join(self.PWD, d)] = {
                        volumes['C:/Users/Jaco.Jansen/code/hackathon2017/{}'.format(d)] = {
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
@click.option('--logs_path', type=click.STRING)
def main(host, remove, logs_path):
    develk = DevElk(host)
    develk.remove_containers = remove
    develk.logs_path = logs_path
    develk.run()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)-7s - %(name)-8s [%(funcName)s:%(lineno)d] :: %(message)s')
    coloredlogs.install(level='DEBUG')
    main()
