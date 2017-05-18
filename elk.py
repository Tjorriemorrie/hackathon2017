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
    keep_existing = False

    def __init__(self, host, pull_images):
        """setup arguments and connect"""
        with open(self.FILE_CONFIG, 'r') as f:
            self.config = ruamel.yaml.safe_load(f)
            logger.info('Loaded configuration')
        # logger.info('{}'.format(json.dumps(self.config, indent=4, default=str)))

        self.host = host
        logger.info('host: {}'.format(self.host))

        self.docker = docker.from_env()
        logger.info('connected to docker')

        self.network = None
        self.containers = {}

        logger.info('pull images? {}'.format(pull_images))
        if pull_images:
            for name, image in self.config['images'].items():
                logger.info('pulling new image for {}'.format(image['url']))
                self.docker.images.pull(image['url'])
                try:
                    self.docker.containers.get(image['name']).remove(force=True)
                except docker.errors.NotFound:
                    pass
            logger.info('docker images: {}'.format(self.docker.images.list()))

    def run(self):
        """Run"""
        # logger.info('{}'.format(os.environ))
        # logger.debug('{}'.format(vars(self)))
        # return
        self.clear_logs()
        self.load_logs()

        self.start_network()
        self.start_containers()

        logger.info('Launching Kibana...')
        webbrowser.open('http://localhost:5601')

        logger.info('running')
        try:
            while True:
                time.sleep(1)
                self.load_logs()
        except KeyboardInterrupt:
            logger.info('shutting down gracefully...')
            self.clear_logs()
            self.stop_containers()

    def clear_logs(self):
        """Clear current log directory"""
        if self.keep_existing:
            logger.info('Keeping existing logs: not clearing')
            return

        logger.info('clearing logs from directory...')
        for root, dirs, files in os.walk(os.path.join(self.PWD, 'logs'), topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
                logger.debug('removed {}'.format(name))

    def load_logs(self):
        """Load logs"""
        if self.keep_existing:
            logger.info('Keeping existing logs: not loading')
            return

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
                    container.stop(timeout=10)
                    break
                except:
                    logger.debug('retrying stopping {}...'.format(container.name))

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
@click.option('--host', type=click.STRING)
@click.option('--remove', is_flag=True)
@click.option('--keep', is_flag=True)
@click.option('--pull', is_flag=True)
def main(host, remove, keep, pull):
    host = host or os.getenv('ELK_HOST', 'localhost')
    pull_images = pull or os.getenv('ELK_PULL', False)
    develk = DevElk(host, pull_images)
    develk.remove_containers = remove or os.getenv('ELK_REMOVE', False)
    develk.keep_existing = keep or os.getenv('ELK_KEEP', False)
    develk.run()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)-7s - %(name)-8s [%(funcName)s:%(lineno)d] :: %(message)s')
    coloredlogs.install(level='DEBUG')
    main()
