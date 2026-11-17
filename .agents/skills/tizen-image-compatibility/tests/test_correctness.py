"""Synthetic correctness fixtures. No target ELF is executed on the host."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
from test_framework import Environment
from compat.core import InputError, hash_file, read_manifest, validate_config, write_json
from compat.elf import collect_elf, parse_readelf, target_abi_matches
from compat.compare import compare_elf, dependency_checks, advanced_abi
from compat.debuginfo import debug_source
from compat.coverage import coverage_report
from compat.images import Image
from compat.testing import run_matrix, run_target
from compat.semantic import semantic_probe, compare_semantics
from compat.report import build_results


def symbol(name, binding='GLOBAL', kind='FUNC'):
    return dict(name=name, binding=binding, visibility='DEFAULT', type=kind, size=0)


def obj(path, needed=(), imports=(), exports=(), **kw):
    return dict(path=path, needed=list(needed), imports=list(imports), exports=list(exports), complete=True,
                machine='Advanced Micro Devices X86-64', **{'class': 'ELF64'}, endianness="2's complement, little endian",
                **kw)


class LoaderTests(Environment):
    def manifest(self, *objects):
        m = self.blank()
        m.update(elf_objects=list(objects), collection_complete=True,
                 loader_environment=dict(model='glibc', cache_complete=True, environment_complete=True, symbol_scope='startup', namespace='base',
                                         default_dirs=['/lib', '/usr/lib'], library_path=[], cache={}))
        return m

    def results(self, m, consumer):
        return dependency_checks(m, 'baseline consumers on candidate', [consumer])

    def test_provider_outside_search_path_is_unresolvable(self):
        c = obj('/bin/app', needed=['libx.so'], type='EXEC')
        m = self.manifest(obj('/opt/private/libx.so', soname='libx.so'))
        f = self.results(m, c)[0]
        self.assertEqual((f['resolution'], f['status']), ('unresolvable_provider', 'INCOMPATIBLE'))
        c['runpath'] = ['$ORIGIN/../opt/private']
        self.assertEqual(self.results(m, c)[0]['resolution'], 'verified')

    def test_missing_and_unknown_environment(self):
        c = obj('/bin/app', needed=['libx.so'], type='EXEC')
        m = self.manifest()
        self.assertEqual(self.results(m, c)[0]['resolution'], 'missing_provider')
        m['loader_environment']['environment_complete'] = False
        self.assertEqual(self.results(m, c)[0]['status'], 'UNKNOWN')
        m['loader_environment']['environment_complete'] = True
        m['collection_complete'] = False
        self.assertEqual(self.results(m, c)[0]['status'], 'UNKNOWN')

    def test_runpath_not_inherited_rpath_is(self):
        c = obj('/bin/app', needed=['libx.so'], type='EXEC', runpath=['/opt'])
        m = self.manifest(obj('/opt/libx.so', needed=['liby.so']), obj('/opt/liby.so'))
        self.assertTrue(any(f['resolution'] == 'unresolvable_provider' for f in self.results(m, c)))
        c['rpath'] = c.pop('runpath')
        self.assertTrue(all(f['resolution'] == 'verified' for f in self.results(m, c)))

    def test_cache_order_and_symlink_alias(self):
        c = obj('/bin/app', needed=['libx.so'], type='EXEC')
        good = obj('/opt/libx-1.so', exports=[symbol('foo')])
        m = self.manifest(good)
        m['filesystem'] = [dict(path='/opt/libx.so', type='symlink', resolved='/opt/libx-1.so')]
        m['loader_environment']['cache'] = {'libx.so': ['/opt/libx.so']}
        self.assertEqual(self.results(m, c)[0]['candidate'], good['path'])
        m['loader_environment']['cache_complete'] = False
        self.assertEqual(self.results(m, c)[0]['status'], 'UNKNOWN')

    def test_relative_paths_and_unknown_tokens_never_verified(self):
        m = self.manifest(obj('/lib/libx.so'))
        for path in ('relative', '$LIB', '$PLATFORM'):
            c = obj('/bin/app', needed=['libx.so'], type='EXEC', runpath=[path])
            self.assertEqual(self.results(m, c)[0]['status'], 'UNKNOWN')

    def test_versioned_import_not_satisfied_by_bare_name(self):
        c = obj('/bin/app', needed=['libx.so'], imports=[symbol('foo@V1')], type='EXEC')
        lib = obj('/lib/libx.so', exports=[symbol('foo')])
        m = self.manifest(lib)
        self.assertEqual(self.results(m, c)[-1]['status'], 'UNKNOWN')  # glibc unversioned interposition requires more context
        lib['exports'] = [symbol('foo@V1')]
        self.assertEqual(self.results(m, c)[-1]['resolution'], 'verified')
        lib['exports'] = [symbol('foo@@V2')]
        self.assertEqual(self.results(m, c)[-1]['status'], 'INCOMPATIBLE')

    def test_requirements_bound_to_provider_not_any_library(self):
        c = obj('/bin/app', needed=['libx.so', 'liby.so'], type='EXEC',
                version_requirements=[dict(file='libx.so', name='V1', flags='none')])
        x = obj('/lib/libx.so', version_definitions=[])
        y = obj('/lib/liby.so', version_definitions=[dict(name='V1')])
        m = self.manifest(x, y)
        self.assertEqual(self.results(m, c)[-1]['resolution'], 'missing_version')
        x['version_definitions'] = [dict(name='V1')]
        self.assertEqual(self.results(m, c)[-1]['resolution'], 'verified')

    def test_weak_and_dso_unresolved_scope_unknown(self):
        m = self.manifest()
        for c in (obj('/bin/app', imports=[symbol('optional', 'WEAK')], type='EXEC'),
                  obj('/lib/plugin.so', imports=[symbol('from_app')], type='DYN')):
            self.assertEqual(self.results(m, c)[-1]['status'], 'UNKNOWN')

    def test_tls_type_and_ifunc(self):
        c = obj('/bin/app', needed=['libx.so'], imports=[symbol('foo', kind='TLS')], type='EXEC')
        x = obj('/lib/libx.so', exports=[symbol('foo', kind='OBJECT')]); m = self.manifest(x)
        self.assertEqual(self.results(m, c)[-1]['resolution'], 'symbol_type_mismatch')
        x['exports'] = [symbol('foo', kind='TLS')]
        self.assertEqual(self.results(m, c)[-1]['resolution'], 'verified')
        x['exports'] = [symbol('foo', kind='IFUNC')]
        self.assertEqual(self.results(m, c)[-1]['status'], 'UNKNOWN')

    def test_missing_loader_and_candidate_own_vs_baseline_imports(self):
        c = obj('/bin/app', interpreter='/lib/ld.so', needed=['libx.so'], imports=[symbol('old')], type='EXEC')
        x = obj('/lib/libx.so', exports=[symbol('new')]); m = self.manifest(x)
        self.assertTrue(any(f['interface'].endswith('dynamic loader') and f['status'] == 'INCOMPATIBLE' for f in self.results(m, c)))
        m['elf_objects'].append(obj('/lib/ld.so'))
        self.assertEqual(self.results(m, c)[-1]['status'], 'INCOMPATIBLE')
        candidate = dict(c, imports=[symbol('new')])
        self.assertEqual(self.results(m, candidate)[-1]['resolution'], 'verified')

    def test_runpath_suppresses_ancestor_rpath_and_preload_is_unknown(self):
        c = obj('/bin/app', needed=['a.so'], type='EXEC', rpath=['/opt'])
        a = obj('/opt/a.so', needed=['b.so'], runpath=['/unavailable'])
        m = self.manifest(a, obj('/opt/b.so'))
        self.assertTrue(any(f['resolution'] == 'unresolvable_provider' for f in self.results(m, c)))
        a.pop('runpath')
        self.assertTrue(all(f['status'] == 'COMPATIBLE' for f in self.results(m, c)))
        m['configurations'] = [dict(path='/etc/ld.so.preload', normalized='/opt/preload.so')]
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in self.results(m, c)))
        m['configurations'] = []
        m['filesystem'] = [dict(path='/bin/app', type='file', mode='4755')]
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in self.results(m, c)))

    def test_dependency_cycle_terminates(self):
        a = obj('/lib/a.so', needed=['b.so']); b = obj('/lib/b.so', needed=['a.so'])
        result = self.results(self.manifest(a, b), a)
        self.assertEqual(len(result), 2)


@unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf') and shutil.which('objcopy'), 'Synthetic ELF fixtures need GCC/binutils')
class RealELFTests(Environment):
    def build(self, name='x', source=None, versions='V1 {}; V2 {} V1;', extra=()):
        src = self.base / (name + '.c')
        src.write_text(source or 'int old_impl(void){return 1;} int new_impl(void){return 2;}\n__asm__(".symver old_impl,foo@V1");\n__asm__(".symver new_impl,foo@@V2");\n')
        vs = self.base / (name + '.map'); vs.write_text(versions)
        lib = self.base / (name + '.so')
        subprocess.run(['gcc', '-shared', '-fPIC', '-g', '-nostdlib', '-Wl,--build-id', '-Wl,-soname,' + name + '.so',
                        '-Wl,--version-script=' + str(vs), str(src), *extra, '-o', str(lib)], check=True, capture_output=True)
        return lib, collect_elf(lib, '/lib/' + name + '.so', self.tools, 'static')

    def test_actual_version_definitions_and_requirements(self):
        path, lib = self.build()
        self.assertIn('foo@@V2', [s['name'] for s in lib['exports']])
        self.assertIn('foo@V1', [s['name'] for s in lib['exports']])
        self.assertEqual(next(v for v in lib['version_definitions'] if v['name'] == 'V2')['parents'], ['V1'])
        _, client = self.build('client', 'extern int foo(void); int use(void){return foo();}', extra=(str(path),))
        imported = next(s for s in client['imports'] if s['name'].startswith('foo'))
        self.assertEqual(imported['version_file'], 'x.so')
        self.assertEqual(imported['version'], 'V2')
        self.assertTrue(any(v['file'] == 'x.so' and v['name'] == 'V2' for v in client['version_requirements']))

    def test_default_version_removal_preserves_explicit_import(self):
        _, a = self.build()
        _, b = self.build('other', 'int old_impl(void){return 1;} int new_impl(void){return 2;}\n__asm__(".symver old_impl,foo@V1");\n__asm__(".symver new_impl,foo@V2");\n')
        b['path'] = a['path']; b['soname'] = a['soname']
        left, right = self.blank(), self.blank(); left['elf_objects'] = [a]; right['elf_objects'] = [b]
        result = compare_elf(left, right)
        self.assertTrue(any(f['interface'] == 'foo:default lookup' and f['status'] == 'INCOMPATIBLE' for f in result))
        self.assertFalse(any(f['interface'] == 'foo@@V2' and f['status'] == 'INCOMPATIBLE' for f in result))
        right['elf_objects'] = [a]
        self.assertFalse(any(f['status'] == 'INCOMPATIBLE' for f in compare_elf(left, right)))

    def test_unversioned_export_can_gain_default_version(self):
        _, a = self.build('bare', 'int foo(void){return 1;}')
        _, b = self.build('versioned', 'int implementation(void){return 1;}\n__asm__(".symver implementation,foo@@V1");')
        b['path'] = a['path']; b['soname'] = a['soname']
        # Focus on the actual foo interface; new implementation-local exports are independent.
        a['exports'] = [v for v in a['exports'] if v['name'] == 'foo']
        left, right = self.blank(), self.blank(); left['elf_objects'] = [a]; right['elf_objects'] = [b]
        result = compare_elf(left, right)
        self.assertFalse(any(f['status'] == 'INCOMPATIBLE' for f in result))
        b['exports'] = [dict(v, name=v['name'].replace('@@', '@')) for v in b['exports']]
        self.assertTrue(any(f['status'] == 'INCOMPATIBLE' and f['interface'] == 'foo' for f in compare_elf(left, right)))

    def test_real_elf_hidden_provider_and_import_failure(self):
        path, lib = self.build()
        _, client = self.build('client', 'extern int foo(void); int use(void){return foo();}', extra=(str(path),))
        lib['path'] = '/opt/hidden/x.so'
        client.update(path='/bin/client', type='EXEC')
        m = self.blank(); m.update(elf_objects=[lib], collection_complete=True,
                                  loader_environment=dict(model='glibc', cache_complete=True, environment_complete=True, symbol_scope='startup', namespace='base', default_dirs=['/lib']))
        self.assertTrue(any(f['resolution'] == 'unresolvable_provider' for f in dependency_checks(m, 'test', [client])))
        client['runpath'] = ['/opt/hidden']
        self.assertTrue(all(f['status'] == 'COMPATIBLE' for f in dependency_checks(m, 'test', [client])))
        lib['exports'] = [s for s in lib['exports'] if not s['name'].startswith('foo')]
        self.assertTrue(any(f['resolution'] == 'missing_symbol' for f in dependency_checks(m, 'test', [client])))

    def test_split_debug_build_id_matching_and_mismatch(self):
        libpath, lib = self.build()
        root = self.base / 'image'; (root / 'lib').mkdir(parents=True)
        shutil.copyfile(libpath, root / 'lib/x.so')
        debug = self.base / 'debug'; bid = lib['build_id']
        dp = debug / 'usr/lib/debug/.build-id' / bid[:2] / (bid[2:] + '.debug')
        dp.parent.mkdir(parents=True)
        subprocess.run(['objcopy', '--only-keep-debug', str(libpath), str(dp)], check=True)
        subprocess.run(['objcopy', '--strip-debug', str(root / 'lib/x.so')], check=True)
        stripped = collect_elf(root / 'lib/x.so', '/lib/x.so', self.tools, 'static')
        image = Image(root, self.workspace, self.tools, 'image')
        self.assertFalse(stripped['debug_info'])
        self.assertEqual(debug_source(stripped, image, [str(debug)], self.tools)['kind'], 'split-build-id')
        wrong, _ = self.build('wrong', 'int different(void){return 99;}')
        subprocess.run(['objcopy', '--only-keep-debug', str(wrong), str(dp)], check=True)
        self.assertIsNone(debug_source(stripped, image, [str(debug)], self.tools))
        self.assertEqual(debug_source(lib, image, [], self.tools)['kind'], 'embedded')


class AbiAndGateTests(Environment):
    def test_arm_eabi_and_float_abi(self):
        prefix = ' Class: ELF32\n Data: little endian\n Machine: ARM\n'
        hard = parse_readelf(prefix + ' Flags: 0x5000400, Version5 EABI, hard-float ABI\n Tag_ABI_VFP_args: VFP registers\n')
        soft = parse_readelf(prefix + ' Flags: 0x5000200, Version5 EABI, soft-float ABI\n')
        missing = parse_readelf(prefix + ' Flags: 0x5000000, Version5 EABI\n')
        older = parse_readelf(prefix + ' Flags: 0x4000400, Version4 EABI, hard-float ABI\n')
        self.assertTrue(target_abi_matches(hard, hard))
        for wrong in (soft, missing, older):
            self.assertFalse(target_abi_matches(hard, wrong))
        conflict = parse_readelf(prefix + ' Flags: 0x5000200\n Tag_ABI_VFP_args: VFP registers\n')
        self.assertFalse(target_abi_matches(hard, conflict))

    def test_no_debug_each_library_counted(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'] = [obj('/lib/a.so'), obj('/lib/b.so')]; b['elf_objects'] = copy.deepcopy(a['elf_objects'])
        self.config['tools']['abidiff'] = False
        result = advanced_abi(a, b, (None, None), self.tools)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in result))
        cov, _ = coverage_report(a, b, result, [], [], self.config)
        self.assertEqual(cov['abi']['applicable'], 4)
        self.assertEqual(cov['abi']['verified'], 2)  # empty collected export surfaces; both layout obligations remain unexecuted
        self.assertTrue(all(u['status'] == 'UNKNOWN' for u in cov['abi']['units'] if u['interface'].endswith(':type-layout')))

    def test_abidiff_exit_bits_with_mock_not_target_results(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'] = [obj('/lib/a.so', debug_info=True)]; b['elf_objects'] = copy.deepcopy(a['elf_objects'])
        root = self.base / 'image'; (root / 'lib').mkdir(parents=True); (root / 'lib/a.so').write_bytes(b'synthetic mocked tool input')
        image = Image(root, self.workspace, self.tools, 'image')
        with patch.object(self.tools, 'path', return_value='/fake/abidiff'):
            for code, status in [(0, 'COMPATIBLE'), (4, 'UNKNOWN'), (8, 'INCOMPATIBLE'), (12, 'INCOMPATIBLE'), (1, 'UNKNOWN'), (2, 'UNKNOWN'), (-1, 'UNKNOWN')]:
                with patch.object(self.tools, 'run', return_value=dict(returncode=code, stdout='mock', stdout_truncated=False, stdout_evidence='a', stderr_evidence='b')):
                    self.assertEqual(advanced_abi(a, b, (image, image), self.tools)[0]['status'], status)

    def test_coverage_not_finding_count_and_missing_tool_not_pass(self):
        from compat.core import finding
        a, b = self.blank(), self.blank(); a['elf_objects'] = [obj('/lib/a.so')]; b['elf_objects'] = copy.deepcopy(a['elf_objects'])
        good = finding('abi', '/lib/a.so', 'dynamic interface surface', 'x', 'x', 'IDENTICAL')
        cov, _ = coverage_report(a, b, [good] * 100, [], [], self.config)
        self.assertEqual(cov['abi']['applicable'], 2)
        self.assertEqual(cov['abi']['coverage_percent'], 50)
        self.assertEqual(cov['abi']['compatibility_percent'], 50)
        self.config['ci']['minimum_coverage'] = {'abi': 75}
        incomplete = copy.deepcopy(b); incomplete['elf_objects'][0]['complete'] = False
        missing, gate = coverage_report(a, incomplete, [], [], [], self.config)
        self.assertEqual(missing['abi']['compatibility_percent'], 0)
        self.assertEqual(gate['status'], 'FAIL')
        layout = finding('abi', '/lib/a.so', 'DWARF type/layout ABI', 1, 1, 'COMPATIBLE')
        _, gate = coverage_report(a, b, [good, layout], [], [], self.config)
        self.assertEqual(gate['status'], 'PASS')
        self.config['analysis']['modes'].remove('abi')
        _, gate = coverage_report(a, b, [], [], [], self.config)
        self.assertEqual(gate['status'], 'FAIL')

    def test_config_new_fields_reject_malformed(self):
        for section, key, value in [('ci', 'minimum_coverage', {'abi': 101}), ('loader', 'environments', {'baseline': {'cache': {'lib.so': ['/../../etc/a']}}}), ('cross_compilation', 'builds', {'gcc': {'sdk': 'baseline'}})]:
            c = copy.deepcopy(self.config); c[section][key] = value
            with self.assertRaises(InputError): validate_config(c)

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Needs synthetic fixture')
    def test_cli_coverage_gate_exit_and_immutability(self):
        from make_synthetic_fixture import create
        from tizen_compat import main
        create(self.base / 'images')
        baseline = self.base / 'images/baseline'
        snapshot = {str(p.relative_to(baseline)): hash_file(p) for p in baseline.rglob('*') if p.is_file() and not p.is_symlink()}
        config = self.base / 'gate.yaml'
        config.write_text('ci:\n  minimum_coverage: {runtime: 100}\n')
        args = ['--baseline', str(baseline), '--candidate', str(baseline), '--config', str(config)]
        self.assertEqual(main(args + ['--output', str(self.base / 'gate-fail')]), 1)
        result = json.loads((self.base / 'gate-fail/results.json').read_text())
        self.assertEqual(result['quality_gate']['status'], 'FAIL')
        config.write_text('ci:\n  minimum_coverage: {runtime: 0}\n')
        self.assertEqual(main(args + ['--output', str(self.base / 'gate-pass')]), 0)
        after = {str(p.relative_to(baseline)): hash_file(p) for p in baseline.rglob('*') if p.is_file() and not p.is_symlink()}
        self.assertEqual(snapshot, after)

    def test_old_manifest_cannot_reuse_legacy_pass(self):
        m = self.blank(); m['test_results'] = [dict(id='old', kind='runtime', image='baseline', status='COMPATIBLE')]
        path = self.base / 'old.json'; write_json(path, m)
        result = read_manifest(path)
        self.assertEqual(result['test_results'][0]['status'], 'UNKNOWN')
        m['schema_version'] = '1.1'; m['loader_environment'] = {'cache': []}; write_json(path, m)
        with self.assertRaises(InputError): read_manifest(path)


class MatrixAndSemanticTests(Environment):
    def images(self):
        roots = []
        for label in ('baseline', 'candidate'):
            root = self.base / label; root.mkdir()
            (root / 'probe').write_text('never executed')
            roots.append(Image(root, self.workspace, self.tools, label))
        return tuple(roots)

    def test_explicit_swapped_compiler_provenance(self):
        self.config['cross_compilation']['builds'] = {
            'gcc': dict(sdk='candidate', reference_image='candidate', provenance='GBS-gcc-candidate'),
            'clang': dict(sdk='baseline', reference_image='baseline', provenance='GBS-clang-reference')}
        _, matrix, _ = run_matrix((self.blank(), self.blank()), self.images(), self.tools, 'static')
        self.assertEqual(matrix[0]['build_sdk'], 'candidate')
        self.assertEqual(matrix[2]['build_sdk'], 'baseline')
        self.assertTrue(all(c['status'] == 'UNKNOWN' for c in matrix))

    def test_adapter_zero_exit_without_receipt_unknown(self):
        roots = self.images()
        self.config['runtime']['environments'] = {'baseline': {'id': 'simulation', 'runner': [sys.executable, '-c', 'print("ok")', '{binary}']}}
        result = run_target(self.config['runtime']['environments']['baseline'], Path('/probe'), [], 'baseline', roots[0], self.tools)
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['stages']['execution_status'], 'UNKNOWN')

    def test_direct_target_runner_forbidden(self):
        roots = self.images()
        with patch.object(self.tools, 'run') as run:
            with self.assertRaises(InputError):
                run_target({'id': 'bad', 'runner': ['{binary}']}, roots[0].root / 'probe', [], 'baseline', roots[0], self.tools)
            run.assert_not_called()

    def test_receipt_hash_and_deployment_validation(self):
        roots = self.images()
        env = {'id': 'simulation', 'runner': ['synthetic-adapter', '{binary}']}
        receipt = dict(schema='tizen-compat-runner/v1', environment_id='simulation', binary_sha256=hash_file(roots[0].root / 'probe'),
                       deployment='ok', execution='ok', returncode=0, stdout='ok', stderr='')
        for mutation, expected in [({}, 'SUCCESS'), ({'binary_sha256': 'wrong'}, 'UNKNOWN'), ({'deployment': 'failed'}, 'UNKNOWN'), ({'environment_id': 'other'}, 'UNKNOWN')]:
            result = dict(returncode=0, stdout=json.dumps(dict(receipt, **mutation)), stdout_truncated=False)
            with patch.object(self.tools, 'run', return_value=result):
                out = run_target(env, Path('/probe'), [], 'baseline', roots[0], self.tools)
            self.assertEqual(out['stages']['execution_status'], expected)

    def test_own_reference_failure_cannot_pass_elsewhere(self):
        roots = self.images()
        self.config['runtime'].update(enabled=True, authorized=True,
            environments={k: {'id': k, 'runner': ['synthetic-adapter', '{binary}']} for k in ('baseline', 'candidate')},
            probes=[dict(name='probe', dimension='runtime', argv=['/probe'])])
        def fake(env, binary, args, label, image, tools):
            return dict(returncode=1 if label == 'baseline' else 0, stdout='same', stderr='', stdout_evidence='a', stderr_evidence='b',
                        stages=dict(deployment_status='SUCCESS', execution_status='SUCCESS', behavior_status='UNKNOWN'))
        with patch('compat.testing.run_target', side_effect=fake):
            tests, _, _ = run_matrix((self.blank(), self.blank()), roots, self.tools, 'runtime')
        self.assertEqual([t['status'] for t in tests], ['UNKNOWN', 'UNKNOWN'])

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Needs synthetic host compiler fixture')
    def test_candidate_build_uses_its_own_reference(self):
        roots = self.images()
        source = self.base / 'minimal.c'; source.write_text('int entry(void){return 0;}')
        library = self.base / 'machine.so'
        subprocess.run(['gcc', '-shared', '-nostdlib', str(source), '-o', str(library)], check=True)
        metadata = collect_elf(library, '/lib/machine.so', self.tools, 'quick')
        sdk = self.base / 'sdk'; sdk.mkdir()
        self.config['cross_compilation'].update(cpp_tests=False, sysroots={'baseline': str(sdk), 'candidate': str(sdk)},
            compilers={'gcc': {'c': shutil.which('gcc')}}, builds={'gcc': dict(sdk='candidate', reference_image='candidate', provenance='synthetic-swapped')},
            probes=[dict(name='minimal', source=str(source), language='c', flags=['-nostdlib', '-Wl,-e,entry'])])
        self.config['runtime'].update(enabled=True, authorized=True,
            environments={k: {'id': k, 'runner': ['simulated-only', '{binary}']} for k in ('baseline', 'candidate')})
        for own_code in (1, 0):
            manifests = (self.blank(), self.blank())
            for m in manifests: m['elf_objects'] = [metadata]
            def fake(env, binary, args, label, image, tools):
                return dict(receipt_sha256=hash_file(binary), returncode=own_code if label == 'candidate' else 0, stdout='same', stderr='', stdout_evidence='a', stderr_evidence='b',
                            stages=dict(deployment_status='SUCCESS', execution_status='SUCCESS', behavior_status='UNKNOWN'))
            with patch('compat.testing.run_target', side_effect=fake):
                tests, matrix, _ = run_matrix(manifests, roots, self.tools, 'full')
            runtime = [t for t in tests if t['kind'] == 'runtime']
            self.assertEqual(len(runtime), 2)
            self.assertTrue(all(t['reference_image'] == 'candidate' and t['build_sdk'] == 'candidate' for t in runtime))
            self.assertEqual([t['status'] for t in runtime], ['UNKNOWN', 'UNKNOWN'] if own_code else ['COMPATIBLE', 'COMPATIBLE'])
            # Missing built-in C probe must prevent complete matrix credit.
            self.assertTrue(all(c['runtime_status'] == 'UNKNOWN' for c in matrix))

    def test_optional_semantic_evidence_not_whole_api_pass(self):
        source = self.base / 'header.c'; source.write_text('int f(void);')
        ast = dict(kind='TranslationUnitDecl', inner=[dict(kind='FunctionDecl', name='f', type={'qualType': 'int (void)'})])
        result = dict(returncode=0, stdout=json.dumps(ast), stdout_truncated=False, stdout_evidence='a', stderr_evidence='b')
        with patch.object(self.tools, 'run', return_value=result):
            sem = semantic_probe(['configured-clang', '--sysroot=/synthetic'], source, self.tools)
        self.assertTrue(sem['complete'])
        test = dict(name='header:/usr/include/a.h', semantic=sem)
        self.assertEqual(compare_semantics(test, test)['status'], 'UNKNOWN')
        result['returncode'] = 1
        with patch.object(self.tools, 'run', return_value=result):
            self.assertFalse(semantic_probe(['clang'], source, self.tools)['complete'])


class ExplicitToolIntegrationTests(Environment):
    build = RealELFTests.build
    @unittest.skipUnless(os.environ.get('COMPAT_TEST_ABIDIFF'), 'Set COMPAT_TEST_ABIDIFF to run real libabigail integration')
    def test_real_abidiff_embedded_and_split_layout_break(self):
        self.config['tools']['abidiff'] = os.environ['COMPAT_TEST_ABIDIFF']
        before, a = self.build('abiold', 'struct data { int x; }; int f(struct data *p){return p->x;}')
        after, b = self.build('abinew', 'struct data { long long x; }; int f(struct data *p){return p->x;}')
        roots = []
        for label, path in (('baseline', before), ('candidate', after)):
            root = self.base / label; (root / 'lib').mkdir(parents=True)
            shutil.copyfile(path, root / 'lib/a.so')
            roots.append(Image(root, self.workspace, self.tools, label))
        a['path'] = b['path'] = '/lib/a.so'
        left, right = self.blank(), self.blank(); left['elf_objects'] = [a]; right['elf_objects'] = [b]
        self.assertEqual(advanced_abi(left, left, (roots[0], roots[0]), self.tools)[0]['status'], 'COMPATIBLE')
        self.assertEqual(advanced_abi(left, right, tuple(roots), self.tools)[0]['status'], 'INCOMPATIBLE')
        for label, root, data in zip(('baseline', 'candidate'), roots, (a, b)):
            bid = data['build_id']; debug = self.base / (label + '-debug')
            dest = debug / '.build-id' / bid[:2] / (bid[2:] + '.debug'); dest.parent.mkdir(parents=True)
            subprocess.run(['objcopy', '--only-keep-debug', str(root.root / 'lib/a.so'), str(dest)], check=True)
            subprocess.run(['objcopy', '--strip-debug', str(root.root / 'lib/a.so')], check=True)
            data['debug_info'] = False
            self.config['debuginfo']['roots'][label] = [str(debug)]
        result = advanced_abi(left, right, tuple(roots), self.tools)[0]
        self.assertEqual(result['status'], 'INCOMPATIBLE', result)
        self.assertEqual(result['debug_coverage']['baseline']['kind'], 'split-build-id')

    @unittest.skipUnless(os.environ.get('COMPAT_TEST_CLANG'), 'Set COMPAT_TEST_CLANG to run real Clang semantic/ARM integration')
    def test_real_clang_ast_and_arm(self):
        clang = os.environ['COMPAT_TEST_CLANG']
        src = self.base / 'semantic.c'; src.write_text('typedef int value; value public_api(value x);')
        sem = semantic_probe([clang], src, self.tools)
        self.assertTrue(sem['complete'])
        self.assertTrue(any(d['name'] == 'public_api' for d in sem['declarations']))
        src.write_text('double f(double x) { return x + 1.; }')
        artifacts = []
        for target in ('armv7-linux-gnueabihf', 'armv7-linux-gnueabi'):
            output = self.base / (target + '.o')
            result = self.tools.run([clang, '--target=' + target, '-c', str(src), '-o', str(output)])
            self.assertEqual(result['returncode'], 0, result['stderr'])
            artifacts.append(collect_elf(output, output.name, self.tools, 'quick'))
        self.assertEqual(artifacts[0]['arm_abi']['float'], 'hard')
        self.assertFalse(target_abi_matches(*artifacts))


if __name__ == '__main__':
    unittest.main()
