import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kstack.cli import ROOT
from kstack.engine import discover, assess, promote, rollback
from kstack.state import read_json, write_json, lock_state
from kstack.transaction import commit_generation, recover
from kstack.portfolio import export_lock, inspect_lock
from kstack.feedback import record, summary
from kstack.hosts import inspect_host
from test_engine import FakeGitHub, PATH, REPO, ID, SHA, CONTENT
from kstack.security import digest


class LifecycleExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / 'state'

    def test_generation_commit_and_undo(self):
        commit_generation(self.state, {'a': {'name': 'anything'}}, [{'version': 1}], 1, {})
        self.assertEqual(read_json(self.state / 'active.json')['a']['name'], 'anything')
        self.assertEqual(recover(self.state), {'recovered': False})
        self.assertEqual(read_json(self.state / 'snapshots/000001.json'), {})

    def test_rollback_interrupted_transaction(self):
        # Simulate a crash after the snapshot and active file were committed.
        write_json(self.state / 'history.json', [{'version': 1}])
        write_json(self.state / 'active.json', {'before': True})
        write_json(self.state / 'pending-transaction.json', {
            'active': {'before': True}, 'history': [{'version': 1}], 'snapshot': 2,
            'snapshot_before': None, 'snapshot_existed': False})
        write_json(self.state / 'snapshots/000002.json', {'before': True})
        write_json(self.state / 'active.json', {'after': True})
        result = recover(self.state)
        self.assertTrue(result['recovered'])
        self.assertEqual(read_json(self.state / 'active.json'), {'before': True})
        self.assertFalse((self.state / 'snapshots/000002.json').exists())
        self.assertEqual(read_json(self.state / 'history.json'), [{'version': 1}])

    def test_corrupt_transaction_rejected(self):
        write_json(self.state / 'pending-transaction.json', {'other': 'data'})
        with self.assertRaisesRegex(ValueError, 'Invalid transaction'):
            recover(self.state)

    def test_version_mismatch_prevents_transaction(self):
        with self.assertRaises(ValueError):
            commit_generation(self.state, {}, [], 1, {})

    def test_atomicity_when_write_fails(self):
        from kstack import transaction
        original = transaction.write_json
        count = {'n': 0}
        def fail_once(path, data):
            if path.name == 'active.json' and count['n'] == 0:
                count['n'] += 1
                raise OSError('simulated failure')
            return original(path, data)
        with patch.object(transaction, 'write_json', side_effect=fail_once):
            with self.assertRaises(OSError):
                commit_generation(self.state, {'after': True}, [{'version': 1}], 1, {})
        self.assertEqual(read_json(self.state / 'active.json'), {})
        self.assertEqual(read_json(self.state / 'history.json'), [])
        self.assertFalse((self.state / 'pending-transaction.json').exists())

    def test_portable_lock_validated(self):
        self.state.mkdir()
        target = self.state / 'approved.json'
        self.assertTrue(export_lock(self.state, target, dry_run=True)['ok'])
        self.assertFalse(target.exists())
        export_lock(self.state, target, dry_run=False)
        self.assertTrue(inspect_lock(target, self.state)['ok'])

    def test_lock_fails_if_object_missing(self):
        write_json(self.state / 'active.json', {ID: {'name': 'high-value-audit',
                   'repository': REPO, 'path': PATH, 'commit': SHA, 'content_sha256': digest(CONTENT)}})
        with self.assertRaisesRegex(ValueError, 'missing'):
            export_lock(self.state, self.state / 'lock.json')
        file = self.state / 'objects' / (digest(CONTENT) + '.md')
        file.parent.mkdir(parents=True)
        file.write_text(CONTENT)
        out = self.state / 'lock.json'
        export_lock(self.state, out, dry_run=False)
        self.assertTrue(inspect_lock(out, self.state)['ok'])
        file.write_text('modified')
        self.assertFalse(inspect_lock(out, self.state)['ok'])

    def test_lockfile_rejects_duplicate_names(self):
        lock = {'format': 1, 'skills': []}
        info = {'id': ID, 'name': 'high-value-audit', 'repository': REPO, 'path': PATH,
                'commit': SHA, 'content_sha256': digest(CONTENT)}
        lock['skills'] = [info, dict(info, id='test/test:skills/x/SKILL.md', repository='test/test', path='skills/x/SKILL.md')]
        file = self.state / 'lock.json'
        write_json(file, lock)
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            inspect_lock(file, self.state)

    def test_outcome_tracking_is_self_reported(self):
        item = {'project_type': 'web', 'category': 'correctness', 'skills': ['evolve'],
                'result': 'passed', 'evidence_note': 'Verified fixture with a passing local regression suite.'}
        record(self.state, item)
        self.assertEqual(summary(self.state)['by_skill']['evolve']['samples'], 1)
        self.assertIn('Self-reported', summary(self.state)['interpretation'])
        self.assertEqual(read_json(self.state / 'outcomes.json')[0]['origin'], 'user-reported-not-independently-verified')

    def test_host_status_does_not_claim_live_invocation(self):
        project = self.state / 'project'
        project.mkdir(parents=True)
        x = inspect_host(ROOT, self.state, 'codex', 'project', project)
        self.assertFalse(x['kstack_installed_integrity'])
        self.assertFalse(x['invocation_verified'])
        self.assertFalse(x['implicit_activation_verified'])


class SchedulingAndRouting(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state = Path(tmp.name) / "state"

    def test_scheduler_is_weekly_and_timezone_aware(self):
        import datetime as dt
        from kstack.scheduler import eligibility, mark_run
        now = dt.datetime(2026, 10, 19, 1, 0, tzinfo=dt.timezone.utc)
        a = eligibility(self.state, now=now)
        self.assertTrue(a['eligible'])
        self.assertTrue(a['monthly_deep_review'])
        mark_run(self.state, a['week_start'], outcome='completed')
        self.assertFalse(eligibility(self.state, now=now)['eligible'])
        another = dt.datetime(2026, 10, 26, 1, 0, tzinfo=dt.timezone.utc)
        self.assertTrue(eligibility(self.state, now=another)['eligible'])

    def test_scheduler_rejects_naive_time(self):
        import datetime as dt
        from kstack.scheduler import eligibility
        with self.assertRaises(ValueError):
            eligibility(self.state, now=dt.datetime(2026,10,19))

    def test_bootstrap_instructions_preserve_existing(self):
        from kstack.project import install_instructions
        project = self.state / 'project'
        project.mkdir(parents=True)
        (project / 'AGENTS.md').write_text('User instructions must survive.\n')
        dry = install_instructions(project)
        self.assertTrue(dry['dry_run'])
        self.assertEqual((project / 'AGENTS.md').read_text(), 'User instructions must survive.\n')
        updated = install_instructions(project, dry_run=False)
        self.assertTrue(any(x['action']=='updated' for x in updated['changes']))
        self.assertIn('User instructions must survive', (project / 'AGENTS.md').read_text())
        again = install_instructions(project, dry_run=False)
        self.assertTrue(all(x['action']=='unchanged' for x in again['changes']))

    def test_bootstrap_rejects_broken_markers(self):
        from kstack.project import install_instructions
        project = self.state / 'project'
        project.mkdir(parents=True)
        (project / 'AGENTS.md').write_text('<!-- KSTACK:START --> without end')
        with self.assertRaises(ValueError):
            install_instructions(project, dry_run=False)

    def test_queue_fairness_across_sources(self):
        from kstack.engine import discover
        from kstack.queue import queue
        class Many:
            def repository(self, repo):return {'default_branch':'main'}
            def head(self, repo, branch):return 'a'*40
            def tree(self, repo, commit):
                return [{'path':f'skills/x{i}/SKILL.md','type':'blob'} for i in range(10)]
        data = {'sources':[{'repository':'good/a','paths':['skills/']},
                           {'repository':'good/b','paths':['skills/']}]}
        r = discover(Many(), data, self.state, max_candidates=3)
        self.assertEqual(len(r['changed']),3)
        self.assertTrue(any('good/a' in x for x in r['changed']))
        self.assertTrue(any('good/b' in x for x in r['changed']))
        self.assertEqual(queue(self.state)['pending'],3)


class DeliveryPreflight(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / 'repo'
        self.project.mkdir()
        self.state = self.root / 'state'
        def git(*args):
            return subprocess.run(['git','-C',str(self.project),*args],
                                  capture_output=True, check=True, text=True).stdout.strip()
        import subprocess
        self.git = git
        git('init','-q')
        git('config','user.email','fixtures@example.org')
        git('config','user.name','Fixture')
        (self.project/'kstack.json').write_text(json.dumps({'verification_commands':[['python','-c','print("ok")']]}))
        git('add','.')
        git('-c','commit.gpgsign=false','commit','-qm','fixture')

    def test_delivery_requires_explicit_approval_and_fresh_checks(self):
        from kstack.delivery import delivery_readiness
        from kstack.verification import verify_project
        first = delivery_readiness(self.project,self.state,'Itskorrah/example',authorised=True)
        self.assertFalse(first['ready_for_host_adapter'])
        result = verify_project(self.project,self.state,apply=True)
        self.assertTrue(result['ok'])
        result2 = delivery_readiness(self.project,self.state,'Itskorrah/example',authorised=False)
        self.assertIn('authorisation',str(result2['blockers']))
        passed = delivery_readiness(self.project,self.state,'Itskorrah/example',authorised=True)
        self.assertTrue(passed['ready_for_host_adapter'])
        self.assertEqual(passed['action'],'none: advisory preflight only')
        (self.project/'records.py').write_text('print("changed")')
        self.assertFalse(delivery_readiness(self.project,self.state,'Itskorrah/example',authorised=True)['ready_for_host_adapter'])

    def test_delivery_rejects_other_repository_formats(self):
        from kstack.delivery import delivery_readiness
        with self.assertRaises(ValueError):
            delivery_readiness(self.project,self.state,'https://evil.example.com/x')
        with self.assertRaises(ValueError):
            delivery_readiness(self.project,self.state,'Itskorrah/repo','../main')


class WeeklyRunnerLocalAcceptance(unittest.TestCase):
    def test_weekly_scans_once_with_fake_upstreams(self):
        import json
        import tempfile
        from io import StringIO
        from contextlib import redirect_stdout
        from kstack.weekly import main
        class API:
            def repository(self, repo):
                return {'default_branch': 'main', 'archived': False}
            def head(self, repo, branch):
                return 'f' * 40
            def tree(self, repo, sha):
                return [{'type': 'blob', 'path': 'skills/example/SKILL.md'}]
        with tempfile.TemporaryDirectory() as tmp:
            output = StringIO()
            with redirect_stdout(output):
                status = main(['--state', tmp, '--run', '--limit', '10'], api=API())
            self.assertEqual(status, 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data['execution'], 'ran')
            self.assertGreater(len(data['discovery']['changed']), 0)
            output2 = StringIO()
            with redirect_stdout(output2):
                second = main(['--state', tmp, '--run', '--limit', '10'], api=API())
            self.assertEqual(second, 0)
            self.assertEqual(json.loads(output2.getvalue())['execution'], 'skipped')
