import requests
import base64
import json
import logging
from datetime import datetime
from django.conf import settings
from django.db import models
from .models import MpesaTransaction, MpesaWithdrawal

logger = logging.getLogger(__name__)

class MpesaService:
    def __init__(self, consumer_key, consumer_secret, shortcode, passkey, is_sandbox=True):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.shortcode = shortcode
        self.passkey = passkey
        self.is_sandbox = is_sandbox
        self.access_token = None
        self.token_expires_at = None

    def get_access_token(self):
        """Get access token from M-Pesa"""
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token

        try:
            # Encode credentials
            credentials = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()

            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            headers = {
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json'
            }

            response = requests.get(f"{base_url}/oauth/v1/generate?grant_type=client_credentials", headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                # Token expires in 3600 seconds (1 hour), we'll refresh 5 minutes early
                self.token_expires_at = datetime.now().timestamp() + 3300
                logger.info("M-Pesa access token obtained successfully")
                return self.access_token
            else:
                logger.error(f"Failed to get access token: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None

    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK push for payment"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}

        try:
            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Generate password
            password_str = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": f"{settings.SITE_URL}/api/mpesa/callback/",
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }

            response = requests.post(f"{base_url}/mpesa/stkpush/v1/processrequest", json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"STK push initiated: {data}")
                return data
            else:
                try:
                    error_data = response.json()
                    error_code = error_data.get('errorCode', 'Unknown')
                    error_msg = error_data.get('errorMessage', 'Unknown error')
                    logger.error(f"STK push failed with code {error_code}: {error_msg}")
                    return {'error': error_data}
                except json.JSONDecodeError:
                    logger.error(f"STK push failed: {response.text}")
                    return {'error': response.text}

        except Exception as e:
            logger.error(f"Error in STK push: {str(e)}")
            return {'error': str(e)}

    def stk_push_query(self, checkout_request_id):
        """Query STK push status"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}

        try:
            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Generate password
            password_str = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }

            response = requests.post(f"{base_url}/mpesa/stkpushquery/v1/query", json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"STK push query result: {data}")
                return data
            else:
                logger.error(f"STK push query failed: {response.text}")
                return {'error': response.text}

        except Exception as e:
            logger.error(f"Error in STK push query: {str(e)}")
            return {'error': str(e)}

    def b2c_payment(self, phone_number, amount, remarks):
        """Business to Customer (B2C) payment - for withdrawals"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}

        try:
            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Generate password
            password_str = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "InitiatorName": "api",  # This should be configured in M-Pesa
                "SecurityCredential": self._get_security_credential(),
                "CommandID": "BusinessPayment",
                "Amount": int(amount),
                "PartyA": self.shortcode,
                "PartyB": phone_number,
                "Remarks": remarks,
                "QueueTimeOutURL": f"{settings.SITE_URL}/api/mpesa/b2c-timeout/",
                "ResultURL": f"{settings.SITE_URL}/api/mpesa/b2c-result/",
                "Occasion": "Withdrawal"
            }

            response = requests.post(f"{base_url}/mpesa/b2c/v1/paymentrequest", json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"B2C payment initiated: {data}")
                return data
            else:
                logger.error(f"B2C payment failed: {response.text}")
                return {'error': response.text}

        except Exception as e:
            logger.error(f"Error in B2C payment: {str(e)}")
            return {'error': str(e)}

    def _get_security_credential(self):
        """Generate security credential for B2C"""
        # In production, this should be the encrypted initiator password
        # For now, we'll use a placeholder
        return base64.b64encode(self.passkey.encode()).decode()

    def b2c_payment_query(self, conversation_id):
        """Query B2C payment status"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}

        try:
            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "ConversationID": conversation_id,
                "OriginatorConversationID": conversation_id,
                "InitiatorName": "api",
                "SecurityCredential": self._get_security_credential(),
                "CommandID": "TransactionStatusQuery",
                "TransactionID": conversation_id,
                "PartyA": self.shortcode,
                "IdentifierType": "4",
                "ResultURL": f"{settings.SITE_URL}/api/mpesa/b2c-result/",
                "QueueTimeOutURL": f"{settings.SITE_URL}/api/mpesa/b2c-timeout/",
                "Remarks": "Transaction status query",
                "Occasion": "Query"
            }

            response = requests.post(f"{base_url}/mpesa/transactionstatus/v1/query", json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"B2C payment query result: {data}")
                return data
            else:
                logger.error(f"B2C payment query failed: {response.text}")
                return {'error': response.text}

        except Exception as e:
            logger.error(f"Error in B2C payment query: {str(e)}")
            return {'error': str(e)}

    def process_withdrawal(self, phone_number, amount, user):
        """Process a withdrawal request"""
        try:
            # Create withdrawal record
            withdrawal = MpesaWithdrawal.objects.create(
                user=user,
                amount=amount,
                phone_number=phone_number,
                status='pending'
            )

            # Initiate B2C payment
            result = self.b2c_payment(
                phone_number=phone_number,
                amount=amount,
                remarks=f"Withdrawal to {phone_number}"
            )

            if 'error' not in result:
                # Update withdrawal with M-Pesa details
                withdrawal.checkout_request_id = result.get('CheckoutRequestID')
                withdrawal.merchant_request_id = result.get('MerchantRequestID')
                withdrawal.response_code = result.get('ResponseCode')
                withdrawal.response_description = result.get('CustomerMessage')
                withdrawal.save()

                logger.info(f"Withdrawal initiated successfully: {withdrawal.id}")
                return {
                    'success': True,
                    'withdrawal_id': withdrawal.id,
                    'message': 'Withdrawal request initiated successfully'
                }
            else:
                # Update withdrawal as failed
                withdrawal.status = 'failed'
                withdrawal.response_description = result['error']
                withdrawal.save()

                logger.error(f"Withdrawal failed: {result['error']}")
                return {
                    'success': False,
                    'error': result['error']
                }

        except Exception as e:
            logger.error(f"Error processing withdrawal: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_withdrawal_balance(self, user):
        """Calculate available balance for withdrawal"""
        from .models import MpesaTransaction, Expense

        # Get total saved (completed transactions)
        total_saved = MpesaTransaction.objects.filter(
            user=user,
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        # Get total expenses
        total_expenses = Expense.objects.filter(user=user).aggregate(
            total=models.Sum('amount')
        )['total'] or 0

        # Available balance = total saved - total expenses
        available_balance = total_saved - total_expenses

        return max(0, available_balance)  # Don't allow negative balance

    def test_connection(self):
        """Test M-Pesa API connectivity"""
        try:
            access_token = self.get_access_token()
            if access_token:
                logger.info("M-Pesa API connection test successful")
                return {'success': True, 'message': 'API connection successful'}
            else:
                return {'success': False, 'error': 'Failed to get access token'}
        except Exception as e:
            logger.error(f"API connection test failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def test_credentials(self):
        """Test M-Pesa credentials validity"""
        try:
            result = self.get_access_token()
            if result:
                return {'success': True, 'message': 'Credentials are valid'}
            else:
                return {'success': False, 'error': 'Invalid credentials'}
        except Exception as e:
            return {'success': False, 'error': f'Credential test failed: {str(e)}'}

    def query_stk_push_status(self, checkout_request_id):
        """Query STK push status"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}

        try:
            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Generate password
            password_str = f"{self.shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }

            response = requests.post(f"{base_url}/mpesa/stkpushquery/v1/query", json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"STK push query result: {data}")
                return data
            else:
                logger.error(f"STK push query failed: {response.text}")
                return {'error': response.text}

        except Exception as e:
            logger.error(f"Error in STK push query: {str(e)}")
            return {'error': str(e)}

    def query_b2c_status(self, conversation_id):
        """Query B2C payment status"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}

        try:
            # Determine base URL
            base_url = "https://sandbox.safaricom.co.ke" if self.is_sandbox else "https://api.safaricom.co.ke"

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "ConversationID": conversation_id,
                "OriginatorConversationID": conversation_id,
                "InitiatorName": "api",
                "SecurityCredential": self._get_security_credential(),
                "CommandID": "TransactionStatusQuery",
                "TransactionID": conversation_id,
                "PartyA": self.shortcode,
                "IdentifierType": "4",
                "ResultURL": f"{settings.SITE_URL}/api/mpesa/b2c-result/",
                "QueueTimeOutURL": f"{settings.SITE_URL}/api/mpesa/b2c-timeout/",
                "Remarks": "Transaction status query",
                "Occasion": "Query"
            }

            response = requests.post(f"{base_url}/mpesa/transactionstatus/v1/query", json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"B2C payment query result: {data}")
                return data
            else:
                logger.error(f"B2C payment query failed: {response.text}")
                return {'error': response.text}

        except Exception as e:
            logger.error(f"Error in B2C payment query: {str(e)}")
            return {'error': str(e)}
