"""AGPL-3.0-only. Synthetic Windows acceptance checks; no real account, key or chat access."""
from pathlib import Path
import contextlib, hashlib, json, os, sqlite3, subprocess, sys, tempfile

ROOT=Path(__file__).resolve().parents[1]
READER=ROOT/'projects/rion-wechat-reader'
HUB=ROOT/'projects/wechat-intelligence-hub'
sys.path[:0]=[str(READER),str(HUB)]
import rion_wechat_reader as reader
from windows_privacy import safe, restrict
from sqlcipher3 import dbapi2 as cipher

def check(value,label,checks):
    if not value:raise AssertionError(label)
    checks.append(label)

def main():
    checks=[]
    check(reader.self_test(True)['passed'],'reader_sqlcipher_roundtrip_and_read_only',checks)
    with tempfile.TemporaryDirectory(prefix='wechat-windows-synthetic-') as tmp:
        base=Path(tmp);data=base/'虚构数据 with spaces';data.mkdir()
        key='11'*32  # Public synthetic fixture key; never used for a real account.
        def encrypted(name,sql):
            path=data/name
            with contextlib.closing(cipher.connect(str(path))) as con:
                con.execute('PRAGMA cipher_log_level = NONE')
                con.execute(f'PRAGMA key="x\'{key}\'"')
                con.executescript(sql);con.commit()
            return path
        contact=encrypted('contact.db',"""
          CREATE TABLE contact(id INTEGER PRIMARY KEY,username TEXT,nick_name TEXT,remark TEXT,alias TEXT,description TEXT,local_type INTEGER);
          INSERT INTO contact VALUES(1,'fixture_customer','示例客户','示例客户','','',1),(2,'fixture_owner','示例本人','我','','',1);
        """)
        session=encrypted('session.db',"""
          CREATE TABLE SessionTable(username TEXT,type INTEGER,unread_count INTEGER,summary TEXT,last_timestamp INTEGER,sort_timestamp INTEGER,last_msg_type INTEGER,last_msg_sub_type INTEGER,last_msg_sender TEXT,last_sender_display_name TEXT);
          INSERT INTO SessionTable VALUES('fixture_customer',1,1,'询价',1788000000,1788000000,1,0,'fixture_customer','示例客户');
        """)
        table='Msg_'+hashlib.md5(b'fixture_customer').hexdigest()
        message=encrypted('message_0.db',f"""
          CREATE TABLE Name2Id(user_name TEXT PRIMARY KEY,is_session INTEGER);
          INSERT INTO Name2Id(rowid,user_name,is_session) VALUES(1,'fixture_customer',1),(2,'fixture_owner',1);
          CREATE TABLE "{table}"(local_id INTEGER PRIMARY KEY,server_id INTEGER,local_type INTEGER,sort_seq INTEGER,real_sender_id INTEGER,create_time INTEGER,status INTEGER,message_content TEXT,compress_content TEXT);
          INSERT INTO "{table}" VALUES(1,101,1,1,1,1788000000,0,'询价：虚构产品两件',''),(2,102,1,2,2,1788000001,0,'报价：虚构金额100元','');
        """)
        auxiliary=encrypted('auxiliary.db','CREATE TABLE synthetic_aux(value TEXT);')
        wrong=encrypted('wrong.db','CREATE TABLE synthetic_wrong(value TEXT);')
        config=base/'config/config.json';keys=base/'config/keys.json'
        reader.secure_write_json(keys,{'keys':{str(p):key for p in [contact,session,message,auxiliary]}|{str(wrong):'22'*32}})
        reader.secure_write_json(config,{'contact_db':str(contact),'session_db':str(session),'message_dbs':[str(message)],'self_username':'fixture_owner','keys_file':str(keys)})
        before=config.read_bytes()
        try:reader.secure_write_json(config,{'unexpected':True})
        except reader.ReaderError:pass
        else:raise AssertionError('existing_config_not_overwritten')
        check(config.read_bytes()==before,'existing_config_not_overwritten',checks)
        check(safe(keys),'windows_private_key_acl',checks)
        if os.name=='nt':
            import win32security as ws
            unsafe=base/'broad-access-probe.txt';unsafe.write_text('synthetic')
            acl=ws.ACL();acl.AddAccessAllowedAce(ws.ACL_REVISION,0x1F01FF,ws.ConvertStringSidToSid('S-1-1-0'))
            ws.SetNamedSecurityInfo(str(unsafe),ws.SE_FILE_OBJECT,ws.DACL_SECURITY_INFORMATION|ws.PROTECTED_DACL_SECURITY_INFORMATION,None,None,acl,None)
            check(not safe(unsafe),'reject_world_readable_key_material',checks)
            restrict(unsafe)
        db=reader.DatabaseSet(config)
        check(len(reader.search_messages(db,'询价',None,10,0,None,None))==1,'encrypted_unicode_search',checks)
        history=reader.timeline(db,'fixture_customer',10,0,None,None)
        check(len(history)==2 and any(r['from_me'] for r in history),'timeline_and_sender_identity',checks)
        discovery=reader.discover_databases(data,20,keys)
        check(discovery['unclassified_readable_count']==1 and discovery['unresolved_database_count']==1,'unclassified_readable_and_wrong_key_distinguished',checks)
        fixture_launcher=base/'fixture reader.py'
        fixture_launcher.write_text('import runpy,sys\nsys.path.insert(0,'+repr(str(READER))+')\nsys.argv=['+repr(str(READER/'rion_wechat_reader.py'))+',"--config",'+repr(str(config))+',*sys.argv[1:]]\nrunpy.run_path(sys.argv[0],run_name="__main__")\n',encoding='utf-8')
        profile=base/'profile/profile.json';reader.secure_write_json(profile,{'owner_aliases':['示例本人'],'context':{'setup_status':'needs_context'}})
        profile_before=profile.read_bytes()
        out=base/'report';radar=base/'index/radar.db'
        command=[sys.executable,'-X','utf8',str(ROOT/'windows/launch.py'),'hub','--profile',str(profile),'chat-search','询价','--since','2026-01-01','--until','2027-01-01','--wechat-cli',str(fixture_launcher),'--db',str(radar),'--out',str(out)]
        environment=dict(os.environ,WECHAT_HUB_COMPAT_DIR=str(base/'compatibility'))
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60,cwd=base,env=environment)
        if result.returncode:raise RuntimeError('Synthetic Hub integration failed: '+result.stderr)
        with contextlib.closing(sqlite3.connect(radar)) as con:
            check(con.execute('SELECT count(*) FROM messages').fetchone()[0]==1,'reader_to_hub_persistent_index',checks)
            check(con.execute('PRAGMA quick_check').fetchone()[0]=='ok','index_integrity',checks)
        check(profile.read_bytes()==profile_before,'existing_profile_preserved',checks)
        check(safe(radar),'windows_private_index_acl',checks)
        # Prove shell metacharacters stay query data when Hub invokes a Python Reader.
        import wechat_intelligence_hub as hub
        sentinel=base/'must-not-exist.txt'
        payload=hub.run_json_command([str(fixture_launcher),'search','not_found & echo unsafe > '+str(sentinel),'--limit','1'])
        check(payload.get('ok') and not sentinel.exists(),'reader_arguments_not_shell_interpreted',checks)
        report=base/'html-demo'
        for rel in ['final_report.md','group-daily/group_daily_topics.md','group-daily/group_daily_groups.md','contact-daily/contact_daily_brief.md','group-daily/cross_group_links.md']:
            p=report/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# 虚构示例\n\n不是实际微信数据。\n',encoding='utf-8')
        from report_bundle_flagship import render_report_bundle
        html,_,_=render_report_bundle(report,title='虚构自检报告')
        text=html.read_text(encoding='utf-8')
        check(all(f'data-route-link="{route}"' in text for route in ['overview','groups','contacts','radar']),'four_section_html_rendering',checks)
    print(json.dumps({'status':'passed','synthetic_only':True,'checks':checks},ensure_ascii=False))

if __name__=='__main__':main()
