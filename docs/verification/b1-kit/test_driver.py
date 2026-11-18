"""Safety checks for the account-only manual acceptance helper."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('b1_driver',Path(__file__).with_name('run_b1.py'))
b1=importlib.util.module_from_spec(spec);spec.loader.exec_module(b1)


class Safety(unittest.TestCase):
    def test_owner_sid_is_refused(self):
        with self.assertRaisesRegex(b1.B1Error,'WRONG_ACCOUNT'):
            b1.guard({'OwnerSid':'owner','TestSid':'test','TestName':'Test'},'owner',Path.cwd())

    def test_only_test_sid_passes(self):
        b1.guard({'OwnerSid':'owner','TestSid':'test','TestName':'Test'},'test',Path.cwd())

    def test_model_and_other_tool_requests_are_refused_before_send(self):
        rpc=object.__new__(b1.RPC)
        for method,params in [('turn/start',{}),('mcpServer/tool/call',{'server':'obscura','tool':'start_run','arguments':{}})]:
            with self.assertRaisesRegex(b1.B1Error,'FORBIDDEN_RPC'):
                rpc.call(method,params)

    def test_user_scope_and_real_agents_path_are_required(self):
        with tempfile.TemporaryDirectory(prefix='b1-helper-test-') as directory:
            root=Path(directory)
            rows=[dict(name=n,path=str(root/n/'SKILL.md'),scope='user') for n in b1.NAMES]
            reply=dict(data=[dict(skills=rows,errors=[])])
            self.assertEqual(len(b1.validate_skills(reply,root)),5)
            rows[0]['scope']='repo'
            with self.assertRaisesRegex(b1.B1Error,'SKILLS_NOT_FROM_SYSTEM_USER_AGENTS'):
                b1.validate_skills(reply,root)
            rows[0]['scope']='user';rows[0]['path']=str(root.parent/'outside/SKILL.md')
            with self.assertRaisesRegex(b1.B1Error,'SKILLS_NOT_FROM_SYSTEM_USER_AGENTS'):
                b1.validate_skills(reply,root)


if __name__=='__main__':unittest.main()
