"""Integration tests use disposable profiles, never the user's Zen profile."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zen arc2 test ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.profile = self.base / 'profile with spaces'
        self.profile.mkdir()
        (self.profile / 'unrelated.txt').write_text('keep me')
        self.env = dict(os.environ, HOME=str(self.base), XDG_CONFIG_HOME=str(self.base / 'config'))

    def run_install(self, answers='y\n', args=None):
        return subprocess.run(['bash', str(ROOT / 'install.sh'), *(args if args is not None else ['--profile', str(self.profile)])],
                              input=answers, text=True, capture_output=True, env=self.env)

    def test_full_install_and_idempotency(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in json.loads((ROOT / 'manifest.json').read_text())['files']:
            self.assertEqual(hashlib.sha256((self.profile / entry['path']).read_bytes()).hexdigest(), entry['sha256'])
        prefs = (self.profile / 'user.js').read_bytes()
        result = self.run_install()
        self.assertIn('already installed', result.stdout)
        self.assertEqual((self.profile / 'user.js').read_bytes(), prefs)
        self.assertEqual((self.profile / 'unrelated.txt').read_text(), 'keep me')

    def existing(self):
        (self.profile / 'chrome').mkdir()
        (self.profile / 'chrome/userChrome.css').write_text('old style')
        (self.profile / 'chrome/other.css').write_text('untouched')
        (self.profile / 'user.js').write_bytes(b'// other customization\r\nuser_pref("test.keep", true);\r\n')

    def test_decline_overwrite_has_no_side_effects(self):
        self.existing()
        result = self.run_install('y\nn\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Cancelled', result.stdout)
        self.assertEqual((self.profile / 'chrome/userChrome.css').read_text(), 'old style')
        self.assertFalse((self.profile / 'chrome/CONFIG.css').exists())
        self.assertEqual(len(list(self.profile.glob('.zen-arc2-backup-*'))), 0)

    def test_overwrite_backup_and_preserve_unrelated(self):
        self.existing()
        old = (self.profile / 'user.js').read_bytes()
        result = self.run_install('y\ny\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        backup, = self.profile.glob('.zen-arc2-backup-*')
        self.assertEqual((backup / 'chrome/userChrome.css').read_text(), 'old style')
        self.assertEqual((backup / 'user.js').read_bytes(), old)
        self.assertTrue((self.profile / 'user.js').read_bytes().startswith(old))
        self.assertEqual((self.profile / 'chrome/other.css').read_text(), 'untouched')

    def test_auto_multiple_profiles_relative_and_absolute(self):
        config = self.base / 'config/zen'
        config.mkdir(parents=True)
        other = config / 'other profile'
        other.mkdir()
        (config / 'profiles.ini').write_text('[Profile0]\nName=Other\nIsRelative=1\nPath=other profile\n'
            f'[Profile1]\nName=Chosen\nIsRelative=0\nPath={self.profile}\n')
        result = self.run_install('2\ny\n', args=[])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.profile / 'chrome/userChrome.css').exists())
        self.assertFalse((other / 'chrome').exists())

    def test_no_profiles(self):
        result = self.run_install(args=[])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No Zen profiles', result.stderr)

    def test_missing_profile(self):
        result = self.run_install(args=['--profile', str(self.base / 'missing')])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'missing').exists())

    def test_cancel_and_eof(self):
        for answer in ['n\n', '']:
            result = self.run_install(answer)
            self.assertFalse((self.profile / 'chrome').exists())

    def test_symlink_and_non_directory_rejected(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (self.profile / 'chrome').symlink_to(outside, target_is_directory=True)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        (self.profile / 'chrome').unlink()
        (self.profile / 'chrome').write_text('not a directory')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)

    def test_userjs_symlink_rejected(self):
        target = self.base / 'secret'
        target.write_text('unchanged')
        (self.profile / 'user.js').symlink_to(target)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), 'unchanged')
        self.assertFalse((self.profile / 'chrome').exists())

    def test_profile_lock_rejected(self):
        (self.profile / 'lock').symlink_to('127.0.0.1:+1234')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.profile / 'chrome').exists())

    def test_corrupt_payload_fails_before_profile_writes(self):
        checkout = self.base / 'checkout with spaces'
        shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        (checkout / 'chrome/CONFIG.css').write_text('tampered')
        result = subprocess.run(['bash', str(checkout / 'install.sh'), '--profile', str(self.profile)],
                                input='y\n', text=True, capture_output=True, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing or changed payload', result.stderr)
        self.assertFalse((self.profile / 'chrome').exists())

    def test_corrupt_preferences_fail_before_writes(self):
        checkout = self.base / 'checkout'
        shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        (checkout / 'theme-prefs.js').write_text('tampered\n')
        result = subprocess.run(['bash', str(checkout / 'install.sh'), '--profile', str(self.profile)],
                                input='y\n', text=True, capture_output=True, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum mismatch', result.stderr)
        self.assertFalse((self.profile / 'chrome').exists())

    def test_custom_ini_and_invalid_selection(self):
        ini = self.base / 'portable profiles.ini'
        ini.write_text(f'[Profile0]\nPath={self.profile}\nIsRelative=0\n[Profile1]\nPath={self.base}\nIsRelative=0\n')
        result = self.run_install('99\n', args=['--profiles-ini', str(ini)])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.profile / 'chrome').exists())


if __name__ == '__main__':
    unittest.main()
