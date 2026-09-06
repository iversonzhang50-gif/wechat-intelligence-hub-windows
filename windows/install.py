"""AGPL-3.0-only. Windows source installation; never reads personal WeChat state."""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, os, platform, subprocess, sys, urllib.request, venv
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wheelhouse',type=Path)
    args=parser.parse_args()
    if os.name!='nt' or sys.version_info[:2]!=(3,12) or platform.machine().lower() not in ('amd64','x86_64'):
        raise SystemExit('This lockfile requires Windows x64 and Python 3.12.')
    runtime=ROOT/'.runtime'
    marker=runtime/'installation.json'
    if runtime.exists():
        if marker.exists():
            print('Existing runtime preserved. Run SelfTest.cmd to verify it.');return
        raise SystemExit('Incomplete runtime preserved. Use another empty extraction directory or inspect the installation failure.')
    venv.EnvBuilder(with_pip=True).create(runtime)
    python=runtime/'Scripts/python.exe'
    wheelhouse=args.wheelhouse
    if wheelhouse is None:
        wheelhouse=runtime/'wheel-cache'
        wheelhouse.mkdir()
        dependencies=json.loads((ROOT/'dependency-provenance.json').read_text(encoding='utf-8'))
        def download(item):
            from urllib.parse import urlsplit
            url=urlsplit(item['url'])
            if url.scheme!='https' or url.hostname!='files.pythonhosted.org':
                raise RuntimeError('Unapproved dependency download host.')
            if Path(item['wheel']).name!=item['wheel']:raise RuntimeError('Invalid wheel filename.')
            print('Downloading verified dependency: '+item['name'],flush=True)
            with urllib.request.urlopen(item['url'],timeout=30) as response:
                blob=response.read(100*1024*1024+1)
            if len(blob)>100*1024*1024 or hashlib.sha256(blob).hexdigest()!=item['sha256']:
                raise RuntimeError('Dependency size/hash mismatch: '+item['name'])
            (wheelhouse/item['wheel']).write_bytes(blob)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(download,dependencies))
    command=[str(python),'-m','pip','--isolated','install','--no-input','--keyring-provider','disabled','--disable-pip-version-check','--require-hashes','--only-binary=:all:','--retries','1','--timeout','30','-r',str(ROOT/'requirements-windows.lock')]
    command.extend(['--no-index','--find-links',str(wheelhouse.resolve())])
    subprocess.run(command,check=True,timeout=600)
    subprocess.run([str(python),'-m','pip','check'],check=True,timeout=60)
    subprocess.run([str(python),'-X','utf8',str(ROOT/'windows/self_test.py')],check=True,timeout=240)
    marker.write_text(json.dumps({'edition':'0.9.2-win-preview.1','python':platform.python_version(),'personal_configuration_changed':False}),encoding='utf-8')
    print('Installed and tested. Existing configuration, keys, Profile and data were not changed.')
if __name__=='__main__':main()
