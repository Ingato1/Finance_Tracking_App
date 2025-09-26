from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime
import json as json_lib
import logging
from .models import MpesaWithdrawal, MpesaTransaction

logger = logging.getLogger(__name__)

@csrf_exempt
def mpesa_b2c_result(request):
    """Handle M-Pesa B2C result callback"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json_lib.loads(request.body.decode('utf-8'))
        logger.info(f"M-Pesa B2C result received: {data}")

        # Extract result data
        result_code = data.get('ResultCode', 1)
        result_desc = data.get('ResultDesc', 'Unknown result')

        if result_code == 0:
            # Success - extract transaction details
            callback_metadata = data.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])

            # Find the withdrawal by conversation ID
            conversation_id = data.get('ConversationID')
            if conversation_id:
                try:
                    withdrawal = MpesaWithdrawal.objects.get(
                        checkout_request_id=conversation_id
                    )
                    withdrawal.status = 'completed'
                    withdrawal.completed_at = datetime.now()

                    # Extract additional details from metadata
                    for item in items:
                        if item.get('Name') == 'TransactionId':
                            withdrawal.transaction_id = item.get('Value')
                        elif item.get('Name') == 'MpesaReceiptNumber':
                            withdrawal.mpesa_receipt_number = item.get('Value')

                    withdrawal.response_description = result_desc
                    withdrawal.save()
                    logger.info(f"Withdrawal {withdrawal.id} completed successfully")

                except MpesaWithdrawal.DoesNotExist:
                    logger.warning(f"Withdrawal not found for result callback: {conversation_id}")
        else:
            # Failed
            conversation_id = data.get('ConversationID')
            if conversation_id:
                try:
                    withdrawal = MpesaWithdrawal.objects.get(
                        checkout_request_id=conversation_id
                    )
                    withdrawal.status = 'failed'
                    withdrawal.response_description = result_desc
                    withdrawal.save()
                    logger.error(f"Withdrawal {withdrawal.id} failed: {result_desc}")

                except MpesaWithdrawal.DoesNotExist:
                    logger.warning(f"Withdrawal not found for failed result: {conversation_id}")

        return JsonResponse({'status': 'success'})

    except Exception as e:
        logger.error(f"Error processing M-Pesa B2C result: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def mpesa_b2c_timeout(request):
    """Handle M-Pesa B2C timeout callback"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json_lib.loads(request.body.decode('utf-8'))
        logger.info(f"M-Pesa B2C timeout received: {data}")

        # Extract timeout data
        conversation_id = data.get('ConversationID')
        if conversation_id:
            try:
                withdrawal = MpesaWithdrawal.objects.get(
                    checkout_request_id=conversation_id
                )
                withdrawal.status = 'failed'
                withdrawal.response_description = 'Transaction timed out'
                withdrawal.save()
                logger.warning(f"Withdrawal {withdrawal.id} timed out")

            except MpesaWithdrawal.DoesNotExist:
                logger.warning(f"Withdrawal not found for timeout: {conversation_id}")

        return JsonResponse({'status': 'success'})

    except Exception as e:
        logger.error(f"Error processing M-Pesa B2C timeout: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def mpesa_stk_callback(request):
    """Handle M-Pesa STK push callback for transaction status updates"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json_lib.loads(request.body.decode('utf-8'))
        logger.info(f"M-Pesa STK callback received: {data}")

        # Extract transaction data
        merchant_request_id = data.get('MerchantRequestID')
        checkout_request_id = data.get('CheckoutRequestID')

        if merchant_request_id and checkout_request_id:
            # Find and update transaction
            try:
                transaction = MpesaTransaction.objects.get(
                    merchant_request_id=merchant_request_id,
                    checkout_request_id=checkout_request_id
                )

                # Update transaction status
                result_code = data.get('ResultCode', 1)
                if result_code == 0:
                    # Success - extract additional details
                    callback_metadata = data.get('CallbackMetadata', {})
                    items = callback_metadata.get('Item', [])

                    transaction.status = 'completed'
                    transaction.completed_at = datetime.now()

                    # Extract additional details from metadata
                    for item in items:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            transaction.mpesa_receipt_number = item.get('Value')
                        elif item.get('Name') == 'TransactionDate':
                            transaction.transaction_date = item.get('Value')
                        elif item.get('Name') == 'PhoneNumber':
                            transaction.phone_number = item.get('Value')

                    transaction.response_description = data.get('ResultDesc', 'Transaction completed')
                    logger.info(f"Transaction {transaction.id} completed successfully")
                else:
                    # Failed
                    transaction.status = 'failed'
                    transaction.response_description = data.get('ResultDesc', 'Transaction failed')
                    logger.error(f"Transaction {transaction.id} failed: {transaction.response_description}")

                transaction.save()

            except MpesaTransaction.DoesNotExist:
                logger.warning(f"Transaction not found for STK callback: {merchant_request_id}")

        return JsonResponse({'status': 'success'})

    except Exception as e:
        logger.error(f"Error processing M-Pesa STK callback: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
