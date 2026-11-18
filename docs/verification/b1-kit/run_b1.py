"""Local B1 acceptance driver. No model turns; only the designated Windows test SID."""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
import webbrowser
from datetime import datetime, timezone

KIT = Path(__file__).resolve().parent
NAMES = tuple('obscura-'+n for n in ('start-story','draft-scene','publish','series-bible','setup-models'))
ALLOWED = frozenset(('initialize','skills/list','thread/start','mcpServerStatus/list','mcpServer/tool/call'))
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class B1Error(RuntimeError):
    pass


def ps(command):
    prefix = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
    return subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',prefix+command],
                          capture_output=True,text=True,encoding='utf-8',errors='replace',
                          creationflags=NO_WINDOW,timeout=90,check=True).stdout.strip()


def current_sid():
    return ps('[Security.Principal.WindowsIdentity]::GetCurrent().User.Value')


def native_profile():
    buffer = ctypes.create_unicode_buffer(32768)
    status = ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, buffer)
    if status:
        raise B1Error('WINDOWS_PROFILE_UNAVAILABLE')
    return Path(buffer.value)


def guard(info, sid, profile):
    if sid != info['TestSid'] or sid == info['OwnerSid']:
        raise B1Error('WRONG_ACCOUNT: увійдіть у Windows як '+info['TestName']+'. У цьому акаунті нічого не змінено.')
    if not profile.is_absolute():
        raise B1Error('PROFILE_MUST_BE_ABSOLUTE')


def app_for_user():
    raw = ps('Get-AppxPackage -Name OpenAI.Codex | Select-Object InstallLocation,PackageFamilyName,Version | ConvertTo-Json -Compress')
    app = json.loads(raw) if raw else None
    if isinstance(app,list):
        app = app[-1] if app else None
    return app


def registered_app(info):
    app = app_for_user()
    if not app:
        manifest = Path(info['App']['InstallLocation'])/'AppxManifest.xml'
        if not manifest.is_file():
            raise B1Error('CODEX_PACKAGE_MISSING: відкрийте Microsoft Store та встановіть Codex у Test.')
        literal = "'"+str(manifest).replace("'","''")+"'"
        try:
            ps('Add-AppxPackage -DisableDevelopmentMode -Register '+literal)
        except subprocess.CalledProcessError:
            raise B1Error('CODEX_REGISTRATION_FAILED: установіть Codex через Microsoft Store саме в Test.') from None
        app = app_for_user()
    if not app:
        raise B1Error('CODEX_NOT_REGISTERED')
    return app


def open_codex(info):
    import xml.etree.ElementTree as ET
    app = registered_app(info)
    manifest = ET.parse(Path(app['InstallLocation'])/'AppxManifest.xml')
    entry = manifest.find('.//{*}Application')
    if entry is None:
        raise B1Error('CODEX_APP_ENTRY_MISSING')
    aumid = app['PackageFamilyName']+'!'+entry.attrib['Id']
    subprocess.Popen(['explorer.exe','shell:AppsFolder\\'+aumid])
    print('Codex відкрито. Увійдіть у свій обліковий запис, потім запустіть 2-RUN-B1.cmd.')
    return 0


def safe_env(profile):
    env = dict(os.environ)
    for key in list(env):
        if key.upper().endswith(('_API_KEY','_TOKEN')):
            env.pop(key,None)
    home = Path(env.get('CODEX_HOME') or profile/'.codex')
    if not home.is_absolute() or not home.resolve().is_relative_to(profile.resolve()):
        raise B1Error('CODEX_HOME_OUTSIDE_TEST_PROFILE')
    env.update(HOME=str(profile),USERPROFILE=str(profile),CODEX_HOME=str(home),
               PYTHONPATH=str(KIT/'checkout/src'),
               PYTHON_KEYRING_BACKEND='keyring.backends.fail.Keyring')
    return env


def validate_skills(answer, skill_root):
    rows = answer.get('data',[])
    if len(rows) != 1 or rows[0].get('errors'):
        raise B1Error('SKILL_DISCOVERY_ERRORS')
    selected = [{k:s[k] for k in ('name','path','scope')} for s in rows[0].get('skills',[]) if s.get('name') in NAMES]
    if len(selected)!=5 or {s['name'] for s in selected}!=set(NAMES):
        raise B1Error('FIVE_SKILLS_NOT_FOUND')
    if any(s['scope']!='user' or not Path(s['path']).resolve().is_relative_to(skill_root.resolve()) for s in selected):
        raise B1Error('SKILLS_NOT_FROM_SYSTEM_USER_AGENTS')
    return selected


class RPC:
    def __init__(self, exe, cwd, env, stderr):
        self.err = stderr.open('w',encoding='utf-8')
        self.p = subprocess.Popen([str(exe),'app-server'],cwd=cwd,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,
            text=True,encoding='utf-8',creationflags=NO_WINDOW)
        self.messages = queue.Queue()
        self.counter = 0
        def reader():
            for line in self.p.stdout:
                try:self.messages.put(json.loads(line))
                except ValueError:pass
            self.messages.put(None)
        threading.Thread(target=reader,daemon=True).start()

    def send(self, data):
        self.p.stdin.write(json.dumps(data)+'\n')
        self.p.stdin.flush()

    def call(self, method, params):
        if method not in ALLOWED or method=='mcpServer/tool/call' and (
                params.get('server')!='obscura' or params.get('tool')!='list_stories' or params.get('arguments')!={}):
            raise B1Error('FORBIDDEN_RPC')
        self.counter += 1
        self.send(dict(id=self.counter,method=method,params=params))
        deadline = time.monotonic()+90
        while time.monotonic()<deadline:
            try:message=self.messages.get(timeout=max(.1,deadline-time.monotonic()))
            except queue.Empty:raise B1Error('RPC_TIMEOUT:'+method) from None
            if message is None:
                raise B1Error('RPC_PROCESS_STOPPED:'+method)
            if message.get('id')==self.counter:
                if 'error' in message:
                    raise B1Error('RPC_FAILED:'+method)
                return message['result']
            if 'id' in message and 'method' in message:
                self.send(dict(id=message['id'],error=dict(code=-32601,message='No interactive actions in B1')))
        raise B1Error('RPC_TIMEOUT:'+method)

    def close(self):
        self.p.terminate()
        try:self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:self.p.kill();self.p.wait()
        self.err.close()


def probe(exe, workspace, env, skill_root, log):
    version = subprocess.run([str(exe),'--version'],env=env,cwd=workspace,
        capture_output=True,text=True,encoding='utf-8',check=True,creationflags=NO_WINDOW).stdout.strip()
    rpc = RPC(exe,workspace,env,log)
    try:
        initialized = rpc.call('initialize',dict(clientInfo=dict(name='obscura_b1_acceptance',version='1')))
        if Path(initialized['codexHome']).resolve()!=Path(env['CODEX_HOME']).resolve():
            raise B1Error('UNEXPECTED_CODEX_HOME')
        rpc.send(dict(method='initialized',params={}))
        skills = validate_skills(rpc.call('skills/list',dict(cwds=[str(workspace)],forceReload=True)),skill_root)
        thread = rpc.call('thread/start',dict(cwd=str(workspace),ephemeral=True,approvalPolicy='never',sandbox='read-only'))
        tid = thread['thread']['id']
        catalog = rpc.call('mcpServerStatus/list',dict(threadId=tid,serverName='obscura',detail='toolsAndAuthOnly'))
        server = next((s for s in catalog.get('data',[]) if s['name']=='obscura'),None)
        tools = server.get('tools',{}) if server else {}
        if len(tools)!=27 or 'list_stories' not in tools or 'get_guide' not in tools:
            raise B1Error('EXPECTED_MCP_CATALOG_NOT_FOUND')
        called = rpc.call('mcpServer/tool/call',dict(threadId=tid,server='obscura',tool='list_stories',arguments={}))
        if called.get('isError') or called.get('structuredContent',{}).get('result')!=[]:
            raise B1Error('LIST_STORIES_NOT_EMPTY_OR_FAILED')
        return dict(version=version,executable=str(exe),codexHome=initialized['codexHome'],
                    skills=skills,discovery_errors=0,tool_names=sorted(tools),list_stories=called,model_turns=0)
    finally:rpc.close()


def accept(info, profile):
    app = registered_app(info)
    env = safe_env(profile)
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    local = profile/'AppData/Local/ObscuraCodexB1'/run_id
    local.mkdir(parents=True)
    evidence = KIT/'results'/run_id
    evidence.mkdir()
    report = dict(source_revision=info['SourceRevision'],test_profile=str(profile),
                  windows_sid=info['TestSid'],started_at=datetime.now(timezone.utc).isoformat(),
                  model_turns=0,status='INCOMPLETE',gui={})
    destination = evidence/'RESULT.json'
    server = None
    logs = []
    try:
        workspace = local/'workspace';workspace.mkdir()
        print('1/4 Встановлюю п’ять скілів штатним установником...')
        installed = subprocess.run([sys.executable,str(KIT/'checkout/scripts/install_codex_skills.py'),'--install'],
            cwd=workspace,env=env,capture_output=True,text=True,encoding='utf-8',creationflags=NO_WINDOW)
        install_report = json.loads(installed.stdout)
        report['install'] = install_report
        if installed.returncode or install_report['result'] not in ('installed','unchanged'):
            raise B1Error('SKILLS_INSTALL_NOT_COMPLETE')
        with socket.socket() as free:
            free.bind(('127.0.0.1',0));port=free.getsockname()[1]
        output = (local/'obscura.log').open('w',encoding='utf-8');logs.append(output)
        server = subprocess.Popen([sys.executable,'-m','storygen.server','--data-dir',str(local/'data'),
            '--env-file',str(local/'absent.env'),'--port',str(port)],
            cwd=workspace,env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{port}'
        for _ in range(150):
            if server.poll() is not None:raise B1Error('OBSCURA_START_FAILED')
            try:
                with http.open(base+'/api/connect/codex/status',timeout=2):break
            except OSError:time.sleep(.2)
        else:raise B1Error('OBSCURA_START_TIMEOUT')
        print('2/4 Зберігаю MCP у налаштуваннях лише акаунта Test...')
        request = urllib.request.Request(base+'/api/connect/codex',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
        with http.open(request,timeout=20) as response:report['mcp_config']=json.load(response)
        print('3/4 Перевіряю обидва backend без модельних запитів...')
        for label,exe in [('cli',KIT/'clients/cli/codex.exe'),('app',Path(app['InstallLocation'])/'app/resources/codex.exe')]:
            print('   '+label+'...')
            report[label] = probe(exe,workspace,env,profile/'.agents/skills',local/(label+'-stderr.log'))
        report['automatic']='PASS'
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('\n4/4 Автоматичні перевірки пройдено. Тепер лише GUI.')
        print('Залиште цю консоль відкритою: нейтральна Obscura працює.')
        print('У Codex повністю закрийте застосунок і знову відкрийте через 1-OPEN-CODEX.cmd.')
        print('Увійдіть, якщо потрібно. У боковій панелі відкрийте Skills/Скіли.')
        for name in NAMES:
            report['gui'][name] = input('Чи є '+name+' у списку? [y/так або n/ні]: ').strip().lower() in ('y','yes','так','т')
        print('Натисніть Ctrl+, → MCP servers/Сервери MCP. Знайдіть obscura.')
        report['gui']['obscura_mcp'] = input('Чи видно enabled obscura? [y/так або n/ні]: ').strip().lower() in ('y','yes','так','т')
        report['status'] = 'PASS' if all(report['gui'].values()) else 'INCOMPLETE'
    except (Exception,KeyboardInterrupt) as error:
        report['error'] = str(error) if isinstance(error,B1Error) else type(error).__name__
        print('Перевірка зупинилась:',report['error'])
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if server:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        for log in logs:log.close()
        print('\nРезультат:',report['status'])
        print('Файл:',destination)
        print('Поверніться у yuriy та напишіть Codex: B1 готово, '+run_id)
        print('Нічого не видаляйте. Вхідні дані й паролі цей звіт не зберігає.')
    return 0 if report['status']=='PASS' else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([],['--open-codex']):
        raise B1Error('UNKNOWN_ARGUMENTS')
    info = json.loads((KIT/'kit-info.json').read_text(encoding='utf-8-sig'))
    guard(info,current_sid(),native_profile())
    safe_env(native_profile())  # Validate profile boundaries before registration or writes.
    return open_codex(info) if argv==['--open-codex'] else accept(info,native_profile())


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        print('B1 не запущено:',str(error) if isinstance(error,B1Error) else type(error).__name__)
        sys.exit(2)
