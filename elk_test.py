from unittest import TestCase
from mock import patch

from elk import DevElk


class TestElk(TestCase):

    def setUp(self):
        super(TestElk, self).setUp()
        self.pull_images = False
        self.host = 'localhost'

    @patch('elk.docker')
    def test_docker_set(self, docker):
        docker.from_env.return_value = 'foo'
        DevElk(self.host, self.pull_images)
        docker.from_env.assert_called()

    @patch('elk.docker')
    def test_localhost_is_set(self, docker):
        develk = DevElk(self.host, self.pull_images)
        self.assertEqual(develk.host, self.host)

    @patch('elk.docker')
    def test_pull_images_is_ran(self, docker):
        DevElk(self.host, True)
        print(type(docker.images.pull))
        docker.images.pull.assert_called()
