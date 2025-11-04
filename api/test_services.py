import unittest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from .services import MpesaService

class TestMpesaService(unittest.TestCase):
    @patch('api.services.requests.get')
    def test_get_access_token_caches_and_refreshes(self, mock_get):
        # First response returns short-lived token
        resp1 = Mock(status_code=200)
        resp1.json.return_value = {'access_token': 'tok1', 'expires_in': 2}
        # Second response returns longer token
        resp2 = Mock(status_code=200)
        resp2.json.return_value = {'access_token': 'tok2', 'expires_in': 3600}
        mock_get.side_effect = [resp1, resp2]

        svc = MpesaService('k', 's', 'sc', 'p', is_sandbox=True)
        t1 = svc.get_access_token()
        self.assertEqual(t1, 'tok1')
        # Force expiry
        svc.token_expires_at = datetime.now() - timedelta(seconds=1)
        t2 = svc.get_access_token()
        self.assertEqual(t2, 'tok2')
        # Ensure requests.get was called twice
        self.assertEqual(mock_get.call_count, 2)

    @patch('api.services.requests.post')
    @patch.object(MpesaService, 'get_access_token', return_value='tok')
    def test_stk_push_handles_invalid_json(self, mock_token, mock_post):
        # Mock post to return status_code 200 but invalid JSON
        resp = Mock(status_code=200)
        resp.json.side_effect = ValueError('No JSON')
        mock_post.return_value = resp

        svc = MpesaService('k', 's', '174379', 'p', is_sandbox=True)
        res = svc.stk_push(phone_number='254700000000', amount=10, account_reference='r', transaction_desc='d')
        self.assertIsInstance(res, dict)
        self.assertIn('error', res)
        self.assertIn('Invalid response', str(res['error']) or '')

if __name__ == '__main__':
    unittest.main()
