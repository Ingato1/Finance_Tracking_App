# finance_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
import base64
import json as json_lib
from .models import Expense, Budget, ExpenseCategory, MpesaTransaction, MpesaSettings, MpesaWithdrawal
from .forms import ExpenseForm, BudgetForm, CustomUserCreationForm, CategoryForm
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully. You can now log in.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome back! You have been logged in successfully.')

            # Redirect to next URL if provided, otherwise to dashboard
            next_url = request.POST.get('next') or request.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'registration/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
def dashboard(request):
    # Get current month's budget
    current_month = timezone.now().replace(day=1)
    try:
        budget = Budget.objects.get(user=request.user, month=current_month)
    except Budget.DoesNotExist:
        budget = None
    
    # Get expenses for the current month
    expenses = Expense.objects.filter(
        user=request.user, 
        date__month=current_month.month,
        date__year=current_month.year
    )
    
    total_spent = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Add percentage calculation
    if budget and budget.amount > 0:
        budget.percentage = (total_spent / budget.amount) * 100
    
    # Check if budget is exceeded
    budget_exceeded = False
    if budget and total_spent > budget.amount:
        budget_exceeded = True
        messages.warning(request, f'You have exceeded your monthly budget of KSH {budget.amount}!')
    
    # Get daily expenses for the last 7 days for the chart
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    daily_expenses = Expense.objects.filter(
        user=request.user,
        date__gte=week_ago,
        date__lte=today
    ).values('date').annotate(total=Sum('amount')).order_by('date')
    
    # Prepare data for the chart
    dates = []
    amounts = []
    for expense in daily_expenses:
        dates.append(expense['date'].strftime('%Y-%m-%d'))
        amounts.append(float(expense['total']))
    
    # Get category-wise spending for the current month
    category_expenses = expenses.values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    categories = []
    category_totals = []
    for expense in category_expenses:
        categories.append(expense['category__name'] or 'Uncategorized')
        category_totals.append(float(expense['total']))
    
    context = {
        'budget': budget,
        'total_spent': total_spent,
        'budget_exceeded': budget_exceeded,
        'dates_json': json.dumps(dates),
        'amounts_json': json.dumps(amounts),
        'categories_json': json.dumps(categories),
        'category_totals_json': json.dumps(category_totals),
        'expenses': expenses.order_by('-date')[:5],  # Recent 5 expenses
    }
    
    return render(request, 'api/dashboard.html', context)

@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Expense added successfully!')
            return redirect('dashboard')
    else:
        form = ExpenseForm()
    return render(request, 'api/add_expense.html', {'form': form})
@login_required
def set_budget(request):
    current_month = timezone.now().replace(day=1)
    
    # Get current budget and expenses
    try:
        current_budget = Budget.objects.get(user=request.user, month=current_month)
        current_expenses_total = Expense.objects.filter(
            user=request.user, 
            date__month=current_month.month,
            date__year=current_month.year
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        remaining_budget = current_budget.amount - current_expenses_total
    except Budget.DoesNotExist:
        current_budget = None
        current_expenses_total = 0
        remaining_budget = 0

    if request.method == 'POST':
        print(f"DEBUG: Raw POST data - {dict(request.POST)}")
        print(f"DEBUG: Month value - '{request.POST.get('month')}'")
        
        form = BudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, 'Budget set successfully!')
            return redirect('dashboard')
        else:
            print(f"DEBUG: Form errors - {form.errors}")
    else:
        initial_data = {
            'month': current_month.strftime('%Y-%m')  # YYYY-MM format
        }
        form = BudgetForm(initial=initial_data)
        print(f"DEBUG: Initial month - '{initial_data['month']}'")
    
    return render(request, 'api/set_budget.html', {
        'form': form,
        'current_budget': current_budget,
        'current_expenses_total': current_expenses_total,
        'remaining_budget': remaining_budget
    })

@login_required
def delete_budget(request, budget_id):
    """Delete a budget with confirmation"""
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)

    if request.method == 'POST':
        # Delete the budget
        budget.delete()
        messages.success(request, 'Budget deleted successfully!')
        return redirect('set_budget')

    # GET request - show confirmation page
    context = {
        'budget': budget,
    }
    return render(request, 'api/delete_budget_confirm.html', context)

@login_required
def expense_list(request):
    frequency = request.GET.get('frequency', 'all')
    
    if frequency == 'daily':
        expenses = Expense.objects.filter(
            user=request.user, 
            date=timezone.now().date()
        )
    elif frequency == 'weekly':
        week_ago = timezone.now().date() - timedelta(days=7)
        expenses = Expense.objects.filter(
            user=request.user, 
            date__gte=week_ago
        )
    elif frequency == 'monthly':
        current_month = timezone.now().date().replace(day=1)
        expenses = Expense.objects.filter(
            user=request.user, 
            date__month=current_month.month,
            date__year=current_month.year
        )
    else:
        expenses = Expense.objects.filter(user=request.user)
    
    expenses = expenses.order_by('-date')
    
    # Calculate total amount
    total_amount = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    return render(request, 'api/expense_list.html', {
        'expenses': expenses,
        'frequency': frequency,
        'total_amount': total_amount  # Add this
    })

@login_required
def spending_analysis(request):
    # Get expenses from the last 6 months
    six_months_ago = (timezone.now() - timedelta(days=180)).replace(day=1)
    
    monthly_expenses = Expense.objects.filter(
        user=request.user,
        date__gte=six_months_ago
    ).extra(
        {'month': "strftime('%Y-%m', date)"}
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')
    
    # Get category breakdown for the current month
    current_month = timezone.now().replace(day=1)
    category_expenses = Expense.objects.filter(
        user=request.user,
        date__month=current_month.month,
        date__year=current_month.year
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    # ADD THIS CODE: Calculate percentages for each category
    total_spent = sum(item['total'] for item in category_expenses)
    for item in category_expenses:
        if total_spent > 0:
            item['percentage'] = (item['total'] / total_spent) * 100
        else:
            item['percentage'] = 0
    
    # Generate spending suggestions
    suggestions = generate_spending_suggestions(request.user)
    
    context = {
        'monthly_expenses': monthly_expenses,
        'category_expenses': category_expenses,  # Now includes percentages
        'suggestions': suggestions,
    }
    
    return render(request, 'api/spending_analysis.html', context)


    
def generate_spending_suggestions(user):
    suggestions = []
    
    # Get current month's expenses
    current_month = timezone.now().replace(day=1)
    expenses = Expense.objects.filter(
        user=user,
        date__month=current_month.month,
        date__year=current_month.year
    )
    
    total_spent = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Check if user has a budget
    try:
        budget = Budget.objects.get(user=user, month=current_month)
        # Convert both values to float for safe comparison
        total_spent_float = float(total_spent)
        budget_amount_float = float(budget.amount)
        
        if total_spent_float > budget_amount_float:
            overspend_amount = total_spent_float - budget_amount_float
            suggestions.append(
                f"You've exceeded your monthly budget by KSH {overspend_amount:.2f}. "
                "Consider reviewing your expenses in high-spending categories."
            )
    except Budget.DoesNotExist:
        suggestions.append(
            "You haven't set a budget for this month. Setting a budget can help you "
            "manage your finances more effectively."
        )
    
    # Analyze category spending
    category_totals = expenses.values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    if category_totals:
        highest_category = category_totals[0]
        # Convert to float for safe calculation
        highest_total = float(highest_category['total'])
        total_spent_float = float(total_spent)
        
        if total_spent_float > 0 and highest_total > total_spent_float * 0.4:  # If more than 40% of spending
            suggestions.append(
                f"Your spending on {highest_category['category__name'] or 'uncategorized expenses'} "
                f"is high (KSH {highest_total:.2f}). Consider looking for ways to reduce "
                "spending in this category."
            )
    
    # Check for frequent small expenses
    small_expenses = expenses.filter(amount__lt=10).count()
    if small_expenses > 20:
        suggestions.append(
            f"You have {small_expenses} small expenses (under KSH 10) this month. These can add up quickly. "
            "Consider tracking them more carefully."
        )
    
    if not suggestions:
        suggestions.append(
            "Your spending patterns look good! Keep tracking your expenses to maintain "
            "good financial health."
        )
    
    return suggestions 
    
@login_required
def expense_charts_data(request):
    # Get daily expenses for the last 30 days
    month_ago = timezone.now().date() - timedelta(days=30)
    
    daily_expenses = Expense.objects.filter(
        user=request.user,
        date__gte=month_ago,
        date__lte=timezone.now().date()
    ).values('date').annotate(total=Sum('amount')).order_by('date')
    
    # Prepare data for the chart
    dates = []
    amounts = []
    for expense in daily_expenses:
        dates.append(expense['date'].strftime('%Y-%m-%d'))
        amounts.append(float(expense['total']))
    
    return JsonResponse({
        'dates': dates,
        'amounts': amounts,
    })
@login_required
def manage_categories(request):
    # Create predefined categories if they don't exist
    predefined_categories = [
        ('food', 'Food'),
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('clothes', 'Clothes'),
        ('transport', 'Transport'),
        ('others', 'Others'),
    ]
    
    for category_id, category_name in predefined_categories:
        if not ExpenseCategory.objects.filter(name=category_id).exists():
            ExpenseCategory.objects.create(
                name=category_id,
                description=f"Predefined category: {category_name}"
            )
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.display_name()}" added successfully!')
            return redirect('manage_categories')
    else:
        form = CategoryForm()
    
    categories = ExpenseCategory.objects.all()
    return render(request, 'api/manage_categories.html', {
        'form': form,
        'categories': categories
    })

@login_required
def delete_category(request, category_id):
    # Prevent deletion of predefined categories
    predefined_categories = ['food', 'utilities', 'rent', 'clothes', 'transport', 'others']
    
    category = get_object_or_404(ExpenseCategory, id=category_id)
    
    # Check if it's a predefined category
    if category.name in predefined_categories:
        messages.error(request, f'Cannot delete predefined category "{category.display_name()}".')
        return redirect('manage_categories')
    
    # Check if the category is used in any expenses
    expenses_count = Expense.objects.filter(category=category).count()
    if expenses_count > 0:
        messages.error(request, f'Cannot delete category "{category.display_name()}" because it is used in {expenses_count} expense(s).')
        return redirect('manage_categories')
    
    # Delete the category
    category_name = category.display_name()
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    return redirect('manage_categories')

# M-Pesa Integration Views
@login_required
def mpesa_settings(request):
    """Configure M-Pesa settings for the user"""
    try:
        settings = MpesaSettings.objects.get(user=request.user)
    except MpesaSettings.DoesNotExist:
        settings = MpesaSettings.objects.create(user=request.user)

    if request.method == 'POST':
        settings.consumer_key = request.POST.get('consumer_key', '')
        settings.consumer_secret = request.POST.get('consumer_secret', '')
        settings.passkey = request.POST.get('passkey', '')
        settings.shortcode = request.POST.get('shortcode', '174379')
        settings.is_sandbox = request.POST.get('is_sandbox') == 'on'
        settings.is_active = request.POST.get('is_active') == 'on'
        settings.save()

        messages.success(request, 'M-Pesa settings updated successfully!')
        return redirect('mpesa_settings')

    context = {
        'settings': settings,
        'is_configured': settings.is_active and all([
            settings.consumer_key, settings.consumer_secret, settings.passkey
        ])
    }
    return render(request, 'api/mpesa_settings.html', context)

@login_required
def mpesa_save_money(request):
    """Handle M-Pesa STK push for saving money"""
    try:
        settings = MpesaSettings.objects.get(user=request.user)
    except MpesaSettings.DoesNotExist:
        messages.error(request, 'Please configure your M-Pesa settings first.')
        return redirect('mpesa_settings')

    if not settings.is_active:
        messages.error(request, 'M-Pesa integration is not active. Please activate it in settings.')
        return redirect('mpesa_settings')

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        amount = request.POST.get('amount')

        if not phone_number or not amount:
            messages.error(request, 'Please provide both phone number and amount.')
            return redirect('mpesa_save_money')

        try:
            amount = float(amount)
            if amount < 1:
                messages.error(request, 'Amount must be at least KSH 1.')
                return redirect('mpesa_save_money')
        except ValueError:
            messages.error(request, 'Please enter a valid amount.')
            return redirect('mpesa_save_money')

        # Format phone number (ensure it starts with 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('254'):
            pass  # Already in correct format
        elif phone_number.startswith('7') or phone_number.startswith('1'):
            phone_number = '254' + phone_number
        else:
            messages.error(request, 'Please enter a valid Kenyan phone number.')
            return redirect('mpesa_save_money')

        # Initiate STK push
        try:
            # Get access token
            url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials" if settings.is_sandbox else "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

            response = requests.get(
                url,
                auth=(settings.consumer_key, settings.consumer_secret),
                timeout=30
            )
            response.raise_for_status()
            access_token = response.json().get('access_token')

            # Generate password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            if settings.is_sandbox and not settings.passkey:
                password_str = f"{settings.shortcode}{timestamp}"
            else:
                password_str = f"{settings.shortcode}{settings.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode('utf-8')

            # STK push payload
            payload = {
                "BusinessShortCode": settings.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": settings.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": f"{settings.SITE_URL}/api/mpesa/callback/",
                "AccountReference": f"Save-{request.user.username}-{timestamp}",
                "TransactionDesc": f"Save Money - {request.user.username}"
            }

            stk_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest" if settings.is_sandbox else "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(stk_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Create transaction record
            MpesaTransaction.objects.create(
                user=request.user,
                amount=amount,
                phone_number=phone_number,
                checkout_request_id=data.get('CheckoutRequestID'),
                merchant_request_id=data.get('MerchantRequestID'),
                response_code=data.get('ResponseCode'),
                response_description=data.get('CustomerMessage'),
                customer_message=data.get('CustomerMessage'),
                status='pending'
            )

            messages.success(request, f'STK push sent to {phone_number}. Please check your phone and enter your M-Pesa PIN.')
            return redirect('mpesa_transactions')

        except requests.exceptions.RequestException as e:
            logger.error(f"STK push failed: {str(e)}")
            messages.error(request, f'Failed to initiate payment: {str(e)}')
            return redirect('mpesa_save_money')

    return render(request, 'api/mpesa_save_money.html')

@login_required
def mpesa_transactions(request):
    """Display M-Pesa transaction history"""
    transactions = MpesaTransaction.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'transactions': transactions,
        'total_saved': sum(t.amount for t in transactions.filter(status='completed'))
    }
    return render(request, 'api/mpesa_transactions.html', context)

@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa callback for transaction status updates"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json_lib.loads(request.body.decode('utf-8'))
        logger.info(f"M-Pesa callback received: {data}")

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
                    transaction.status = 'completed'
                    transaction.transaction_id = data.get('MpesaReceiptNumber')
                    transaction.mpesa_receipt_number = data.get('MpesaReceiptNumber')
                    transaction.completed_at = datetime.now()
                else:
                    transaction.status = 'failed'
                    transaction.response_description = data.get('ResultDesc', 'Transaction failed')

                transaction.save()
                logger.info(f"Transaction {transaction.id} updated to {transaction.status}")

            except MpesaTransaction.DoesNotExist:
                logger.warning(f"Transaction not found for callback: {merchant_request_id}")

        return JsonResponse({'status': 'success'})

    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# M-Pesa Withdrawal Views
@login_required
def mpesa_withdraw_money(request):
    """Handle M-Pesa withdrawal requests"""
    try:
        settings = MpesaSettings.objects.get(user=request.user)
    except MpesaSettings.DoesNotExist:
        messages.error(request, 'Please configure your M-Pesa settings first.')
        return redirect('mpesa_settings')

    if not settings.is_active:
        messages.error(request, 'M-Pesa integration is not active. Please activate it in settings.')
        return redirect('mpesa_settings')

    # Calculate available balance
    from .services import MpesaService
    mpesa_service = MpesaService(
        settings.consumer_key,
        settings.consumer_secret,
        settings.shortcode,
        settings.passkey,
        settings.is_sandbox
    )
    available_balance = mpesa_service.get_withdrawal_balance(request.user)

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        amount = request.POST.get('amount')

        if not phone_number or not amount:
            messages.error(request, 'Please provide both phone number and amount.')
            return redirect('mpesa_withdraw_money')

        try:
            amount = float(amount)
            if amount < 10:
                messages.error(request, 'Minimum withdrawal amount is KSH 10.')
                return redirect('mpesa_withdraw_money')

            if amount > available_balance:
                messages.error(request, f'Insufficient balance. Available: KSH {available_balance:.2f}')
                return redirect('mpesa_withdraw_money')
        except ValueError:
            messages.error(request, 'Please enter a valid amount.')
            return redirect('mpesa_withdraw_money')

        # Format phone number (ensure it starts with 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('254'):
            pass  # Already in correct format
        elif phone_number.startswith('7') or phone_number.startswith('1'):
            phone_number = '254' + phone_number
        else:
            messages.error(request, 'Please enter a valid Kenyan phone number.')
            return redirect('mpesa_withdraw_money')

        # Process withdrawal
        result = mpesa_service.process_withdrawal(phone_number, amount, request.user)

        if result['success']:
            messages.success(request, f'Withdrawal request initiated! Amount: KSH {amount:.2f}')
            return redirect('mpesa_withdrawals')
        else:
            messages.error(request, f'Withdrawal failed: {result["error"]}')
            return redirect('mpesa_withdraw_money')

    context = {
        'available_balance': available_balance,
        'minimum_withdrawal': 10
    }
    return render(request, 'api/mpesa_withdraw_money.html', context)

@login_required
def mpesa_withdrawals(request):
    """Display M-Pesa withdrawal history"""
    withdrawals = MpesaWithdrawal.objects.filter(user=request.user).order_by('-created_at')

    # Calculate totals
    total_withdrawn = withdrawals.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    pending_withdrawals = withdrawals.filter(status='pending').count()

    context = {
        'withdrawals': withdrawals,
        'total_withdrawn': total_withdrawn,
        'pending_withdrawals': pending_withdrawals
    }
    return render(request, 'api/mpesa_withdrawals.html', context)

@csrf_exempt
def mpesa_b2c_callback(request):
    """Handle M-Pesa B2C callback for withdrawal status updates"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json_lib.loads(request.body.decode('utf-8'))
        logger.info(f"M-Pesa B2C callback received: {data}")

        # Extract withdrawal data
        conversation_id = data.get('ConversationID')
        originator_conversation_id = data.get('OriginatorConversationID')

        if conversation_id:
            # Find and update withdrawal
            try:
                withdrawal = MpesaWithdrawal.objects.get(
                    checkout_request_id=conversation_id
                )

                # Update withdrawal status
                result_code = data.get('ResultCode', 1)
                if result_code == 0:
                    withdrawal.status = 'completed'
                    withdrawal.transaction_id = data.get('TransactionId')
                    withdrawal.mpesa_receipt_number = data.get('MpesaReceiptNumber')
                    withdrawal.completed_at = datetime.now()
                    withdrawal.response_description = data.get('ResultDesc', 'Withdrawal completed')
                else:
                    withdrawal.status = 'failed'
                    withdrawal.response_description = data.get('ResultDesc', 'Withdrawal failed')

                withdrawal.save()
                logger.info(f"Withdrawal {withdrawal.id} updated to {withdrawal.status}")

            except MpesaWithdrawal.DoesNotExist:
                logger.warning(f"Withdrawal not found for callback: {conversation_id}")

        return JsonResponse({'status': 'success'})

    except Exception as e:
        logger.error(f"Error processing M-Pesa B2C callback: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)