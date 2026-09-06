"""AGPL-3.0-only. Verify the reviewed source manifest and optional source ZIP."""
from pathlib import Path
import argparse,hashlib,json,re,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--zip',type=Path);args=parser.parse_args()
    manifest=json.loads((ROOT/'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
    known={item['path']:item for item in manifest['files']}
    failures=[]
    for name,item in known.items():
        p=ROOT/name
        if Path(name).is_absolute() or '..' in Path(name).parts:failures.append('invalid_path');continue
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:failures.append('hash:'+name)
        if p.is_symlink():failures.append('symlink:'+name)
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in ('.git','.runtime','__pycache__'))}
    if actual!=set(known)|{'RELEASE-MANIFEST.json'}:failures.append('unexpected_or_missing_source_file')
    if args.zip:
        with zipfile.ZipFile(args.zip) as archive:
            entries={name.split('/',1)[1]:name for name in archive.namelist() if '/' in name and not name.endswith('/')}
            if set(entries)!=set(known)|{'RELEASE-MANIFEST.json'}:failures.append('zip_entry_set_mismatch')
            for name,item in known.items():
                if name not in entries or hashlib.sha256(archive.read(entries[name])).hexdigest()!=item['sha256']:failures.append('zip_hash:'+name)
            if 'RELEASE-MANIFEST.json' not in entries or archive.read(entries['RELEASE-MANIFEST.json'])!=(ROOT/'RELEASE-MANIFEST.json').read_bytes():failures.append('zip_manifest_mismatch')
    if failures:raise SystemExit(json.dumps({'status':'failed','findings':failures},ensure_ascii=False))
    print(json.dumps({'status':'passed','source_files':len(known)+1,'zip_verified':bool(args.zip)}))
if __name__=='__main__':main()
