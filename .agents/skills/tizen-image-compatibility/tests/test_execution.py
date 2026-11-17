"""Test real local tool calls using synthetic inputs; never execute image binaries."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from compat.core import DEFAULTS, Tools
from compat.collect import collect
from compat.images import Image
from compat.packages import collect_packages
from compat.testing import run_matrix
from make_synthetic_fixture import create


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = copy.deepcopy(DEFAULTS)
        self.tools = Tools(self.root / 'report', self.config)
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Needs local GCC/readelf for synthetic fixture')
    def test_real_header_compile_matrix(self):
        create(self.root / 'images')
        images = tuple(Image(self.root / 'images' / label, self.workspace, self.tools, label) for label in ('baseline', 'candidate'))
        manifests = tuple(collect(image, 'SYNTHETIC', label, 'static', self.tools, self.workspace)
                          for image, label in zip(images, ('baseline', 'candidate')))
        # Minimal SDK deliberately cannot build runtime probes; header probes can run.
        sdk = self.root / 'sdk'; (sdk / 'usr/include').mkdir(parents=True)
        # The SDK gets the fixture public header paths below.
        for header in manifests[0]['public_headers']:
            target = sdk / header['path'].lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('int sdk_function(void);\n')
        self.config['cross_compilation']['builds'] = {'gcc': {'sdk': 'candidate', 'reference_image': 'candidate', 'provenance': 'synthetic-gcc-sdk'}}
        self.config['cross_compilation'].update(sysroots={'baseline': str(sdk), 'candidate': str(sdk)},
            compilers={'gcc': {'c': shutil.which('gcc')}}, cpp_tests=False)
        tests, matrix, findings = run_matrix(manifests, images, self.tools, 'full')
        headers = [t for t in tests if t.get('name', '').startswith('header:')]
        self.assertEqual(len(headers), 2)
        self.assertTrue(all(t['status'] == 'COMPATIBLE' for t in headers))
        self.assertTrue(all(c['runtime_status'] == 'UNKNOWN' for c in matrix))
        self.assertTrue(any(t.get('name') == 'c-behavior' and t['status'] == 'UNKNOWN' for t in tests))

    def mock_environments(self):
        adapter = self.root / 'adapter.py'
        adapter.write_text('''import sys, json, hashlib
from pathlib import Path
label = sys.argv[1]
source = Path(sys.argv[3]) / sys.argv[2].lstrip('/')
print(json.dumps(dict(schema='tizen-compat-runner/v1', environment_id='SYNTHETIC-ADAPTER-' + label,
    binary_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), deployment='ok', execution='ok',
    returncode=0, stdout='base' if label == 'baseline' else 'different', stderr='')))
''')
        images = []
        for label in ('baseline', 'candidate'):
            path = self.root / label; path.mkdir()
            (path / 'never-executed').write_text('synthetic adapter input; never execute')
            images.append(Image(path, self.workspace, self.tools, label))
        self.config['runtime'].update(enabled=True, authorized=True,
            environments={label: {'id': 'SYNTHETIC-ADAPTER-' + label,
                                  'runner': [sys.executable, str(adapter), '{image}', '{binary}', '{rootfs}']}
                          for label in ('baseline', 'candidate')},
            probes=[{'name': 'synthetic-output', 'dimension': 'commands', 'argv': ['/never-executed']}])
        manifests = tuple({'public_headers': [], 'elf_objects': [], 'test_results': []} for _ in range(2))
        return tuple(images), manifests

    def test_authorized_adapter_detects_behavior_difference(self):
        images, manifests = self.mock_environments()
        tests, matrix, findings = run_matrix(manifests, images, self.tools, 'runtime')
        self.assertEqual(len(tests), 2)
        self.assertEqual(tests[0]['status'], 'COMPATIBLE')
        self.assertEqual(tests[1]['status'], 'INCOMPATIBLE')
        self.assertEqual(findings[1]['dimension'], 'commands')
        self.assertTrue(all(c['status'] == 'UNKNOWN' for c in matrix))

    def test_unauthorized_adapter_is_never_run(self):
        images, manifests = self.mock_environments()
        self.config['runtime']['authorized'] = False
        tests, matrix, findings = run_matrix(manifests, images, self.tools, 'runtime')
        self.assertFalse(tests)
        self.assertFalse(self.tools.records)

    def test_runtime_exclusion_prevents_execution(self):
        images, manifests = self.mock_environments()
        self.config['analysis']['modes'].remove('runtime')
        tests, matrix, findings = run_matrix(manifests, images, self.tools, 'runtime')
        self.assertFalse(tests)
        self.assertFalse(self.tools.records)

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('g++'), 'Needs host C/C++ compilers for trusted probe self-test')
    def test_trusted_probe_sources_on_host(self):
        # These are our own reviewed source files, not image binaries. This validates
        # probe implementation only, never reports a Tizen runtime pass.
        for language, compiler, standard in [('c', 'gcc', 'c11'), ('cpp', 'g++', 'c++17')]:
            artifact = self.root / ('probe-' + language)
            result = subprocess.run([shutil.which(compiler), '-Wall', '-Wextra', '-Werror', '-std=' + standard,
                str(SKILL / 'assets/probes' / ('behavior.' + language)), '-pthread', '-ldl', '-lm', '-o', str(artifact)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(artifact)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])

    @unittest.skipUnless(shutil.which('rpmbuild') and shutil.which('rpm'), 'Needs RPM tools')
    def test_actual_rpm_archive_query(self):
        spec = self.root / 'fixture.spec'
        spec.write_text('''Name: tizen-compat-synthetic
Version: 1.0
Release: 1
Summary: Synthetic test fixture, not Tizen
License: MIT
BuildArch: noarch
Provides: synthetic-interface = 1.0
Requires: synthetic-dependency >= 1
%description
Synthetic package metadata for framework tests only.
%install
mkdir -p %{buildroot}/usr/share/tizen-compat-synthetic
printf synthetic > %{buildroot}/usr/share/tizen-compat-synthetic/test
%files
/usr/share/tizen-compat-synthetic/test
''')
        result = subprocess.run(['rpmbuild', '--define', '_topdir ' + str(self.root / 'rpm-build'), '-bb', str(spec)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        rpm = next((self.root / 'rpm-build/RPMS').rglob('*.rpm'))
        image = Image(rpm, self.workspace, self.tools, 'rpm')
        packages, limits = collect_packages(image, self.tools, self.workspace)
        self.assertFalse(limits, limits)
        self.assertEqual(packages[0]['name'], 'tizen-compat-synthetic')
        self.assertTrue(any(x['name'] == 'synthetic-interface' for x in packages[0]['provides']))
        self.assertTrue(any(x['name'] == 'synthetic-dependency' for x in packages[0]['requires']))
        self.assertIn('/usr/share/tizen-compat-synthetic/test', packages[0]['files'])


if __name__ == '__main__':
    unittest.main()
