"""A backend restart must not forget its recently attempted provider calls."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from backend.tests.test_market_data_live import BatchTests
from backend.src.market_data.live import BusyError,LiveCoordinator

class BudgetPersistenceTests(unittest.TestCase):
 setUp=BatchTests.setUp
 def new_path(self):
  folder=Path.cwd()/'.agent-state/test-budget'/uuid4().hex
  folder.mkdir(parents=True)
  return folder/'budget.json'
 def service_with_budget(self,path):
  return LiveCoordinator(self.fetch,lambda _:False,self.repo,now=lambda:self.now,
                         clock=lambda:self.seconds,budget_path=path)
 def test_restart_keeps_minimum_spacing(self):
  with patch('time.time',return_value=1800000000):
   path=self.new_path()
   self.service_with_budget(path).refresh('FPT')
   restored=self.service_with_budget(path)
   with self.assertRaises(BusyError):restored.refresh('VCB')
   self.assertEqual(self.fetch.call_count,1)
   self.seconds=5;restored.refresh('VCB')
   self.assertEqual(self.fetch.call_count,2)
 def test_corrupt_budget_waits_for_unknown_recent_usage_to_expire(self):
  path=self.new_path();path.write_text('{bad',encoding='utf-8')
  service=self.service_with_budget(path)
  with self.assertRaises(BusyError):service.refresh('FPT')
  self.fetch.assert_not_called()
  self.seconds=60;service.refresh('FPT')
  self.assertIsNone(service.status()['budget_error'])
 def test_failed_provider_attempt_is_restored(self):
  with patch('time.time',return_value=1800000000):
   path=self.new_path();self.fetch.side_effect=RuntimeError('provider-secret')
   with self.assertRaises(RuntimeError):self.service_with_budget(path).refresh('FPT')
   restored=self.service_with_budget(path)
   with self.assertRaises(BusyError):restored.refresh('VCB')
   self.assertEqual(self.fetch.call_count,1)
   self.assertNotIn('provider-secret',str(restored.status()))
 def test_backward_wall_clock_does_not_erase_recent_attempt(self):
  path=self.new_path()
  with patch('time.time',return_value=100):self.service_with_budget(path).refresh('FPT')
  with patch('time.time',return_value=99.5):
   restored=self.service_with_budget(path)
   self.seconds=.5
   with self.assertRaises(BusyError):restored.refresh('VCB')
   self.seconds=4.999
   with self.assertRaises(BusyError):restored.refresh('VCB')
   self.seconds=5;restored.refresh('VCB')
   self.assertEqual(self.fetch.call_count,2)
