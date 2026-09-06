"""AGPL-3.0-only. Explicit opt-in; never replaces existing Skills or engines."""
from pathlib import Path
import argparse,json,os,shutil
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--codex-root',type=Path,default=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))));a=p.parse_args()
    targets=[a.codex_root/'skills'/n for n in ('wechat-cli','wechat-intelligence-hub')]
    if any(t.exists() for t in targets):raise SystemExit('Existing Skills preserved. Review migration in a separate directory; nothing overwritten.')
    for t in targets:
        shutil.copytree(ROOT/'skills'/t.name,t)
        (t/'windows.json').write_text(json.dumps({'package_root':str(ROOT)},ensure_ascii=False),encoding='utf-8')
    print('Skills installed; no existing Profile, credentials or WeChat data changed.')
if __name__=='__main__':main()
