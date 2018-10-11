#!/usr/bin/env python

import fakeaur.server
import glob
import multiprocessing
import os.path
import shutil
import subprocess
import tempfile
import unittest


def FindMesonBuildDir():
    if os.path.exists('.ninja_log'):
        return os.path.curdir

    paths = glob.glob('*/.ninja_log')
    if len(paths) > 1:
        raise ValueError('Multiple build directories found. Unable to proceed.')
    if len(paths) == 0:
        raise ValueError(
                'No build directory found. Have you run "meson build" yet?')

    return os.path.dirname(paths[0])


class HTTPRequest(object):

    def __init__(self, request):
        self.requestline = request.pop(0)
        self.command, self.path, self.request_version = self.requestline.split()

        self.headers = {}
        for line in request:
            if line:
                k, v = line.split(':', 1)
                self.headers[k.lower()] = v.strip()


class TestCase(unittest.TestCase):

    def setUp(self):
        self.build_dir = FindMesonBuildDir()
        self.tempdir = tempfile.mkdtemp()

        self.requests_file = tempfile.NamedTemporaryFile(
                dir=self.tempdir, prefix='requests-').name

        q = multiprocessing.Queue()
        self.server = multiprocessing.Process(
                target=fakeaur.server.Serve, args=(q,))
        self.server.start()
        port = q.get()

        self.baseurl = 'http://localhost:{}'.format(port)


    def tearDown(self):
        self.server.terminate()
        shutil.rmtree(self.tempdir)


    def _ProcessDebugOutput(self):
        self.requests_sent = []
        with open(self.requests_file) as f:
            header_text = []
            for line in f.read().splitlines():
                if not line:
                    self.requests_sent.append(HTTPRequest(header_text))
                    header_text = []
                else:
                    header_text.append(line)

        self.request_uris = [r.path for r in self.requests_sent]


    def Auracle(self, args):
        env = {
            'PATH': '{}/fakeaur:{}'.format(
                os.path.dirname(os.path.realpath(__file__)), os.getenv('PATH')),
            'AURACLE_TEST_TMPDIR': self.tempdir,
            'AURACLE_DEBUG': 'requests:{}'.format(self.requests_file),
        }

        cmdline = [
            os.path.join(self.build_dir, 'auracle'),
            '--baseurl', self.baseurl,
            '--color=never',
            '--chdir', self.tempdir,
        ] + list(args)

        p = subprocess.run(cmdline, env=env, capture_output=True)

        self._ProcessDebugOutput()

        return p


    def assertPkgbuildExists(self, pkgname, git=False):
        self.assertTrue(
                os.path.exists(os.path.join(self.tempdir, pkgname, 'PKGBUILD')))
        if git:
            self.assertTrue(
                    os.path.exists(os.path.join(self.tempdir, pkgname, '.git')))


def main():
    unittest.main()