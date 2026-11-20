"""Execute the real PowerShell helper; mock side effects inside PowerShell."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'scripts/bootstrap-finmind.ps1'


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == 'nt', 'Windows launcher')
class LauncherTests(unittest.TestCase):
    def run_ps(self, body):
        with tempfile.TemporaryDirectory() as temp:
            harness = Path(temp) / 'test.ps1'
            harness.write_text("$ErrorActionPreference='Stop'\n[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)\n. " + quote(SCRIPT) + '\n' + body, encoding='utf-8-sig')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness)], capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(result.stdout.strip().splitlines()[-1])

    def test_actual_consent_defaults_to_decline(self):
        answers = ['y', 'YES', ' c ', 'co', 'CÓ', '', ' ', 'n', 'khong', 'anything']
        code = '$answers = ' + '@(' + ','.join(quote(v) for v in answers) + ")\n"
        code += "$results=@(); foreach($value in $answers) { $script:answer=$value; function Read-Host { return $script:answer }; $results += [bool](Request-InstallConsent @('test')) }; ConvertTo-Json -Compress -InputObject $results"
        self.assertEqual(self.run_ps(code), [True]*5 + [False]*5)

    def test_real_main_branches_never_install_or_launch_without_consent(self):
        cases = [
            ('ready-check', True, True, False, True, True, False, 0, ['state']),
            ('ready-start', True, False, False, True, True, False, 0, ['state','launch']),
            ('missing-check', False, True, True, True, True, False, 1, ['state']),
            ('decline', False, False, False, True, True, False, 1, ['state','consent']),
            ('accept', False, False, True, True, True, False, 0, ['state','consent','install','state','launch']),
            ('install-fail', False, False, True, False, True, False, 1, ['state','consent','install']),
            ('recheck-fail', False, False, True, True, False, False, 1, ['state','consent','install','state']),
            ('blocker', False, False, True, True, True, True, 1, ['state']),
        ]
        for name, ready, check, consent, installed, recheck, blocked, expected, events in cases:
            with self.subTest(name=name):
                flag = lambda value: '$true' if value else '$false'
                code = f"""
$script:events=[Collections.Generic.List[string]]::new(); $script:reads=0
function Get-FinMindState {{
    param($Root); $script:events.Add('state'); $script:reads++
    $ready=if($script:reads -eq 1) {{ {flag(ready)} }} else {{ {flag(recheck)} }}
    [pscustomobject]@{{Ready=$ready; Missing=@($(if(-not $ready){{'dependency'}})); Blockers=@($(if({flag(blocked)}){{'blocked'}}))}}
}}
function Request-InstallConsent {{ param($Items); $script:events.Add('consent'); return {flag(consent)} }}
function Install-FinMindRequirements {{ param($Root,$State); $script:events.Add('install'); return {flag(installed)} }}
function Start-FinMind {{ param($Root); $script:events.Add('launch'); return $true }}
$code=Invoke-FinMind -Root 'C:\test O''Brien & FinMind' -Check:{flag(check)}
[pscustomobject]@{{Code=$code; Events=@($script:events.ToArray())}} | ConvertTo-Json -Compress
"""
                actual = self.run_ps(code)
                self.assertEqual(actual, {'Code':expected, 'Events':events})

    def test_native_probe_preserves_python_arguments(self):
        import sys
        code = '$result = Invoke-FinMindProbe ' + quote(sys.executable) + " @('-B','-c','import sys; print(sys.argv[1])','path with space & apostrophe')\n$result | ConvertTo-Json -Compress"
        self.assertEqual(self.run_ps(code), {'Code':0, 'Text':'path with space & apostrophe'})

    def test_cmd_uses_file_entry_and_preserves_exit_code(self):
        text = (ROOT / 'Chay-FinMind.cmd').read_text(encoding='utf-8')
        self.assertIn('-File "%~dp0scripts\\bootstrap-finmind.ps1"', text)
        self.assertNotIn('-Command', text)
        self.assertIn('exit /b %EXIT_CODE%', text)


if __name__ == '__main__':
    unittest.main()
