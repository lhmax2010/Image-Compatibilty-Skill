"""Compile and freeze reviewed probe recipes in a read-only target SDK sandbox."""
from pathlib import Path
import re
import shutil

from .core import InputError, hash_file, write_json
from .probe_bundle import LEAF, SCHEMA, load


def require(ok, message):
    if not ok:
        raise InputError(message)


def build_bundle(config, output, tools):
    work = output/'work'
    work.mkdir()
    (work/'tmp').mkdir()
    (work/'src').mkdir()
    (work/'out').mkdir()
    bundle = output/'bundle'
    bundle.mkdir()
    sdb_cases = []
    sdk_evidence = {}
    for name, spec in config['sdk'].items():
        host, sysroot, starts = (Path(spec[k]).resolve(strict=True) for k in ('host', 'sysroot', 'startfiles'))
        lock = Path(spec['lock']).resolve(strict=True)
        require(hash_file(lock) == spec['lock_sha256'], f'{name} SDK lock identity differs')
        sdk_evidence[name] = {'host':str(host), 'sysroot':str(sysroot), 'startfiles':str(starts),
                              'lock_sha256':hash_file(lock), 'label': spec['label']}
    inputs = {}
    for path in config['sources']:
        src=Path(path)
        require(src.is_file() and LEAF.fullmatch(src.name) and src.name not in inputs,
                'Expected a unique ordinary source file')
        shutil.copyfile(src, work/'src'/src.name)
        inputs[src.name] = hash_file(work/'src'/src.name)
    build_record = {'sources':inputs,'sdks':sdk_evidence,'steps':[]}
    bwrap = shutil.which('bwrap')
    readelf = shutil.which('readelf')
    require(bwrap and readelf, 'Build requires bwrap and readelf')
    for step in config['steps']:
        name, leaf = step['sdk'],step['out']
        require(LEAF.fullmatch(leaf) and not (work/'out'/leaf).exists(),
                'Compile outputs must be unique flat names')
        spec = config['sdk'][name]
        roots = sdk_evidence[name]
        driver = step['driver']
        require(re.fullmatch(r'/usr/bin/[a-zA-Z0-9_+.-]+', driver) and
                driver in spec['compiler_sha256'] and
                hash_file(Path(roots['host'])/driver[1:]) == spec['compiler_sha256'][driver],
                'Compiler must match the pinned SDK')
        shared_work = ['--bind',str(work),'/work','--ro-bind',str(work/'src'),'/work/src',
                       '--ro-bind',roots['startfiles'],'/work/startfiles']
        argv = [bwrap,'--unshare-user','--unshare-pid','--unshare-net','--die-with-parent','--new-session',
                '--ro-bind',roots['host'],'/','--ro-bind',roots['sysroot'],'/sysroot',*shared_work,
                '--dev','/dev','--proc','/proc','--clearenv','--setenv','PATH','/usr/bin','--setenv','LC_ALL','C',
                '--setenv','TMPDIR','/work/tmp','--setenv','LD_LIBRARY_PATH','/usr/lib64:/lib64:/usr/lib:/lib',
                '--chdir','/work']
        if spec.get('clang_resources'):
            argv += ['--ro-bind',roots['host']+'/usr/lib64/clang/22/include','/sdk-resource/include',
                     '--ro-bind',roots['sysroot']+'/usr/lib/clang/22/lib','/sdk-resource/lib']
        flags = [*step['flags'], '-o', '/work/out/'+leaf]
        result = tools.run([*argv,'--',driver,*flags],timeout=90,max_capture_bytes=512*1024)
        record = {'sdk':name,'driver':driver,'compiler_sha256':spec['compiler_sha256'][driver],
                  'argv':[driver,*flags], 'output':leaf,'returncode':result['returncode'],
                  'expected_returncode':step.get('expected_returncode',0),'error':result['error'],
                  'evidence':[result['stdout_evidence'],result['stderr_evidence']]}
        build_record['steps'].append(record)
        write_json(output/'build.json',build_record)
        require(not result['error'] and result['returncode']==record['expected_returncode'],
                'Unexpected compiler/linker result for '+leaf)
        if result['returncode'] != 0:
            require(step['stderr_contains'] in result['stderr'], 'Linker did not report the specified failure')
            continue
        dest=work/'out'/leaf
        require(dest.is_file() and not dest.is_symlink(), 'Missing build output')
        record['sha256']=hash_file(dest)
        elf=tools.run([readelf,'-W','-h','-A','-l','-d','-V','--dyn-syms',str(dest)],
                      timeout=15,max_capture_bytes=512*1024)
        require(elf['returncode']==0 and not elf['error'], 'ELF verification failed for '+leaf)
        record['elf_evidence']=elf['stdout_evidence']
        record['interpreter']=next(iter(re.findall(r'Requesting program interpreter: (.*?)\]',elf['stdout'])),None)
        record['needed']=re.findall(r'\(NEEDED\).*?\[(.*?)\]',elf['stdout'])
        write_json(output/'build.json',build_record)
    proof = hash_file(output/'build.json')
    by_leaf={r['output']:r for r in build_record['steps'] if r['returncode']==0}
    for case in config['probes']:
        name=case['artifact_id']
        require(LEAF.fullmatch(name),'Invalid artifact ID')
        root=bundle/name
        root.mkdir()
        files={}
        for leaf, source in case['files'].items():
            require(LEAF.fullmatch(leaf) and source in by_leaf, 'Unregistered artifact file')
            shutil.copyfile(work/'out'/source, root/leaf)
            (root/leaf).chmod(0o444)
            files[leaf]=hash_file(root/leaf)
            require(files[leaf] == by_leaf[source]['sha256'], 'Build bytes changed before freeze')
        main=by_leaf[case['files']['probe']]
        sdb_cases.append(case | {'files':files,'elf':{'interpreter':main['interpreter'],'needed':main['needed']},
            'build':{'records':[by_leaf[v] for v in case['files'].values()],'evidence_sha256':proof}})
    manifest=output/'probe-manifest.json'
    write_json(manifest,{'schema':SCHEMA, 'probes':sdb_cases})
    pin=hash_file(manifest)
    load(manifest,pin,bundle)
    return manifest,pin,bundle
