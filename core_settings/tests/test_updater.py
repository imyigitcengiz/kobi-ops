"""Güncelleme modülü testleri."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core_settings.updater import UpdateStatus, check_for_updates, resolve_apply_mode


class UpdaterTests(SimpleTestCase):
    @override_settings(KOBIOPS_DEPLOY_WEBHOOK_URL='https://example.com/hook')
    def test_resolve_apply_mode_webhook_priority(self):
        self.assertEqual(resolve_apply_mode(), 'webhook')

    @patch('core_settings.updater.fetch_remote_commit')
    @patch('core_settings.updater.local_git_commit')
    @patch('core_settings.updater._cache_path')
    def test_update_available_when_commits_differ(self, cache_path, local_git, remote):
        cache_path.return_value = None
        local_git.return_value = ('aaa1111', 'aaa1111111111111111111111111111111111111111')
        remote.return_value = ('bbb2222', 'bbb2222222222222222222222222222222222222222', 'Fix', '2026-01-01T00:00:00Z')
        status = check_for_updates(force=True)
        self.assertTrue(status.update_available)
        self.assertEqual(status.remote_commit, 'bbb2222')

    @patch('core_settings.updater.fetch_remote_commit')
    @patch('core_settings.updater.local_git_commit')
    @patch('core_settings.updater._cache_path')
    def test_up_to_date_when_commits_match(self, cache_path, local_git, remote):
        cache_path.return_value = None
        sha = 'ccc3333333333333333333333333333333333333333'
        local_git.return_value = ('ccc3333', sha)
        remote.return_value = ('ccc3333', sha, 'Same', '2026-01-01T00:00:00Z')
        status = check_for_updates(force=True)
        self.assertFalse(status.update_available)

    def test_update_status_to_dict(self):
        data = UpdateStatus(local_version='1.0.0').to_dict()
        self.assertEqual(data['local_version'], '1.0.0')
