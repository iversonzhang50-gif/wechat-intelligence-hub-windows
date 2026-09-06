"""AGPL-3.0-only. Portable launch, no automatic acquisition or initialization."""
from pathlib import Path
import os, runpy, sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    args=sys.argv[1:]
    if not args or args[0] in ('-h','--help'):
        print('wechat.cmd reader <command> | hub <command> | self-test')
        print('Configuration and keys are reused; no automatic acquisition. See README.md.');return
    mode=args.pop(0)
    if mode=='self-test':
        runpy.run_path(str(ROOT/'windows/self_test.py'),run_name='__main__');return
    choices={'reader':('rion-wechat-reader','rion_wechat_reader.py'),'hub':('wechat-intelligence-hub','wechat_intelligence_hub.py')}
    if mode not in choices:raise SystemExit('Unknown mode. Use reader, hub or self-test.')
    project,filename=choices[mode]
    directory=ROOT/'projects'/project
    sys.path.insert(0,str(directory))
    if mode=='hub':
        os.environ.setdefault('WECHAT_READER_BIN',str(ROOT/'projects/rion-wechat-reader/rion_wechat_reader.py'))
        os.chdir(directory)
    sys.argv=[str(directory/filename),*args]
    runpy.run_path(sys.argv[0],run_name='__main__')
if __name__=='__main__':main()
