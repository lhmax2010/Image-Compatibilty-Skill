"""Exact binding contracts for the bounded glibc Loader observations."""
import re

from .core import InputError

SYMBOL = re.compile(r'[A-Za-z0-9_.$]+')
VERSION = re.compile(r'[A-Za-z0-9_.$+-]+')
PIN = re.compile(r'[a-f0-9]{64}')
SYSTEM_PATH = re.compile(r'/(?:usr/)?lib/[A-Za-z0-9_.+@/-]+')
EVENT = re.compile(
    rb"binding file (\S+) \[(\d+)\] to (\S+) \[(\d+)\]: [^\n]*?symbol `([^']+)'(?: \[([^]\n]+)\])?"
)


def validate_contracts(case):
    contracts = case.get('binding_contracts', [])
    if not isinstance(contracts, list) or len(contracts) > 16:
        raise InputError('Expected at most 16 exact binding contracts')
    keys = set()
    for item in contracts:
        if not isinstance(item, dict) or item.keys() != {'consumer','provider','symbol','version','provider_sha256'}:
            raise InputError('Exact binding contract must specify both endpoints, symbol, version and Provider SHA256')
        for role in ('consumer', 'provider'):
            endpoint = item[role]
            if not isinstance(endpoint, str):
                raise InputError('Invalid binding endpoint')
            if endpoint.startswith('bundle:'):
                name = endpoint.removeprefix('bundle:')
                files = case['files']
                if name not in files or role == 'provider' and (
                        name == 'probe' or files[name] != item['provider_sha256']):
                    raise InputError('Binding endpoint must match a frozen Bundle file')
            elif not SYSTEM_PATH.fullmatch(endpoint) or any(part in ('', '.', '..') for part in endpoint[1:].split('/')):
                raise InputError('Binding endpoint must be a Bundle identity or canonical absolute library path')
        symbol, version, checksum = (item[k] for k in ('symbol','version','provider_sha256'))
        if (not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol)
                or version is not None and (not isinstance(version, str) or not VERSION.fullmatch(version))
                or not isinstance(checksum, str) or not PIN.fullmatch(checksum)):
            raise InputError('Invalid exact symbol, version or Provider SHA256')
        key = (item['consumer'], symbol, version)
        if key in keys:
            raise InputError('Duplicate or ambiguous binding contract for Consumer, symbol and version')
        keys.add(key)
    if contracts and case['runtime_expectation'].get('outcome', 'exit') != 'exit':
        raise InputError('Exact binding contracts require a probe that reaches execution')


def events(log, wanted):
    for consumer, cn, provider, pn, symbol, version in EVENT.findall(log):
        name = symbol.decode('ascii')
        if name in wanted:
            yield dict(consumer=consumer.decode('ascii'), consumer_namespace=int(cn),
                       provider=provider.decode('ascii'), provider_namespace=int(pn),
                       symbol=name, version=version.decode('ascii') or None)


def exact_results(contracts, observed, files, attempt, artifact):
    if not contracts:
        return []

    directory = attempt.directory
    bundle = artifact['files']

    def normalized(path):
        return directory + path[1:] if path.startswith('./') else path

    def endpoint(selector):
        if selector.startswith('bundle:'):
            leaf = selector.removeprefix('bundle:')
            return directory+'/'+leaf, bundle[leaf]
        return selector, None

    def matches(path, selector):
        expected, _ = endpoint(selector)
        path = normalized(path)
        return path == expected or any(
            path in (row['requested'], row['path']) and expected in (row['requested'], row['path'])
            for row in files)

    results = []
    for contract in contracts:
        relevant = [row for row in observed if row['symbol'] == contract['symbol']
                    and row['version'] == contract['version'] and matches(row['consumer'], contract['consumer'])]
        verified = []
        identities = set()
        for row in relevant:
            provider = normalized(row['provider'])
            loaded = next((file for file in files if provider in (file['requested'], file['path'])), None)
            identities.add((row['consumer_namespace'], row['provider_namespace'],
                            loaded['path'] if loaded else provider))
            if (row['consumer_namespace'] == row['provider_namespace'] == 0 and loaded
                    and matches(provider, contract['provider']) and loaded['sha256'] == contract['provider_sha256']):
                verified.append(row | {'loaded_provider': loaded})
        consumer, consumer_pin = endpoint(contract['consumer'])
        if consumer != directory+'/probe' and not any(
                consumer in (file['requested'], file['path']) and (consumer_pin is None or file['sha256'] == consumer_pin)
                for file in files):
            verified = []
        reason = ('AMBIGUOUS_BINDINGS' if len(identities) > 1 else
                  'EXACT_BINDING_OBSERVED' if verified else
                  'UNVERIFIED_PROVIDER_OR_SCOPE' if relevant else 'REQUIRED_BINDING_NOT_OBSERVED')
        results.append({'contract':contract, 'status':'VERIFIED' if reason == 'EXACT_BINDING_OBSERVED' else 'NOT_VERIFIED',
                        'reason':reason, 'matched_event':verified[0] if reason == 'EXACT_BINDING_OBSERVED' else None})
    return results
