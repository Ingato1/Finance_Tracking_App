# finance_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.db.models import Sum, Count, Q, CharField
from django.db.models.functions import Concat
from django.db.models import Value
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
from .views_mpesa_callbacks import mpesa_b2c_result, mpesa_b2c_timeout, mpesa_stk_callback
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
    if budget:
        if budget.amount > 0:
            budget.percentage = (total_spent / budget.amount) * 100
        else:
            budget.percentage = 0
    
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
            month = form.cleaned_data['month']
            amount = form.cleaned_data['amount']

            # Check if budget exists for this user and month
            try:
                budget = Budget.objects.get(user=request.user, month=month)
                budget.amount = amount
                budget.save()
                messages.success(request, 'Budget updated successfully!')
            except Budget.DoesNotExist:
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
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully!')
            return redirect('expense_list')
    else:
        form = ExpenseForm(instance=expense)

    return render(request, 'api/add_expense.html', {'form': form, 'edit': True, 'expense': expense})

@login_required
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)

    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully!')
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def spending_analysis(request):
    # Get expenses from the last 12 months for better trends with select_related
    twelve_months_ago = (timezone.now() - timedelta(days=365)).replace(day=1)

    # Monthly trends data
    monthly_expenses = Expense.objects.filter(
        user=request.user,
        date__gte=twelve_months_ago
    ).select_related('category').annotate(
        month=Concat('date__year', Value('-'), 'date__month', output_field=CharField())
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')

    # Prepare data for charts
    monthly_trends_labels = []
    monthly_trends_data = []

    for expense in monthly_expenses:
        monthly_trends_labels.append(expense['month'])
        monthly_trends_data.append(float(expense['total']))

    # Get category breakdown for the current month
    current_month = timezone.now().replace(day=1)
    category_expenses = Expense.objects.filter(
        user=request.user,
        date__month=current_month.month,
        date__year=current_month.year
    ).select_related('category').values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')

    # Calculate percentages for each category
    total_spent = sum(item['total'] for item in category_expenses) if category_expenses else 0
    category_labels = []
    category_amounts = []

    for item in category_expenses:
        category_name = item['category__name'] or 'Uncategorized'
        category_labels.append(category_name)
        category_amounts.append(float(item['total']))

    # Budget vs Actual comparison - prefetch budgets for last 6 months
    budgets_last_6 = Budget.objects.filter(
        user=request.user,
        month__gte=timezone.now().replace(day=1) - timedelta(days=180),
        month__lte=timezone.now().replace(day=1)
    )
    budget_dict = {b.month: b.amount for b in budgets_last_6}

    budget_comparison_labels = []
    budget_comparison_budget = []
    budget_comparison_actual = []

    # Get last 6 months for budget comparison
    for i in range(5, -1, -1):
        month_date = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_str = month_date.strftime('%Y-%m')

        # Get budget for this month
        budget_amount = float(budget_dict.get(month_date, 0))

        # Get actual spending for this month
        actual_spending = Expense.objects.filter(
            user=request.user,
            date__month=month_date.month,
            date__year=month_date.year
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        budget_comparison_labels.append(month_str)
        budget_comparison_budget.append(budget_amount)
        budget_comparison_actual.append(float(actual_spending))

    # Top spending categories (last 3 months)
    three_months_ago = timezone.now() - timedelta(days=90)
    top_categories = Expense.objects.filter(
        user=request.user,
        date__gte=three_months_ago
    ).select_related('category').values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:5]

    # Calculate percentages
    total_top = sum(item['total'] for item in top_categories) if top_categories else 0
    for item in top_categories:
        item['name'] = item['category__name'] or 'Uncategorized'
        item['amount'] = float(item['total'])
        item['percentage'] = (item['total'] / total_top * 100) if total_top > 0 else 0
        item['trend'] = 'stable'  # Simplified for now

    # Monthly breakdown for detailed table
    monthly_breakdown = []
    for i in range(5, -1, -1):
        month_date = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_str = month_date.strftime('%B %Y')

        # Get budget for this month
        budget_amount = float(budget_dict.get(month_date, 0))

        # Get actual spending for this month
        actual_spending = Expense.objects.filter(
            user=request.user,
            date__month=month_date.month,
            date__year=month_date.year
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        # Get top category for this month
        top_category_data = Expense.objects.filter(
            user=request.user,
            date__month=month_date.month,
            date__year=month_date.year
        ).select_related('category').values('category__name').annotate(
            total=Sum('amount')
        ).order_by('-total').first()

        top_category = top_category_data['category__name'] if top_category_data else 'N/A'

        # Calculate variance
        variance = budget_amount - float(actual_spending)

        monthly_breakdown.append({
            'month': month_str,
            'total_spent': float(actual_spending),
            'budget': budget_amount,
            'variance': variance,
            'top_category': top_category,
            'transaction_count': Expense.objects.filter(
                user=request.user,
                date__month=month_date.month,
                date__year=month_date.year
            ).count()
        })

    # Generate spending suggestions
    suggestions = generate_spending_suggestions(request.user)

    # Financial goals progress (simplified)
    goals = []
    if total_spent > 0:
        # Example goal: Monthly spending limit
        monthly_limit = 50000  # KSH 50,000
        current_progress = min((total_spent / monthly_limit) * 100, 100)
        goals.append({
            'name': 'Monthly Spending Limit',
            'current': total_spent,
            'target': monthly_limit,
            'progress': current_progress,
            'color': 'success' if current_progress <= 100 else 'danger'
        })

    # Predictions (simplified)
    predictions = None
    if len(monthly_trends_data) >= 3 and monthly_trends_data:
        # Simple linear trend prediction
        recent_avg = sum(monthly_trends_data[-3:]) / 3
        if recent_avg > 0:
            predictions = {
                'next_month': recent_avg * 1.05,  # 5% increase
                'trend': 'increasing',
                'change_percent': 5.0,
                'yearly_projection': recent_avg * 12
            }

    # Alerts
    alerts = []
    if total_spent > 0:
        if budget_amount is not None and budget_amount > 0 and total_spent > budget_amount:
            alerts.append({
                'type': 'warning',
                'icon': 'exclamation-triangle',
                'message': f'You have exceeded your monthly budget by KSH {total_spent - budget_amount:.2f}'
            })

    context = {
        'monthly_trends': True,
        'monthly_trends_labels': monthly_trends_labels or [],
        'monthly_trends_data': monthly_trends_data or [],
        'budget_comparison': budget_comparison_labels or [],  # Keep as list for template check
        'budget_comparison_labels': budget_comparison_labels or [],
        'budget_comparison_budget': budget_comparison_budget or [],
        'budget_comparison_actual': budget_comparison_actual or [],
        'category_data': category_labels or [],  # Keep as list for template check
        'category_labels': category_labels or [],
        'category_amounts': category_amounts or [],
        'top_categories': top_categories or [],
        'monthly_breakdown': monthly_breakdown or [],
        'suggestions': suggestions or [],
        'goals': goals or [],
        'predictions': predictions,
        'alerts': alerts or [],
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
        is_active = request.POST.get('is_active') == 'on'

        # Validate credentials when activating
        if is_active:
            if not settings.consumer_key or not settings.consumer_secret or not settings.passkey:
                messages.error(request, 'All M-Pesa credentials (Consumer Key, Consumer Secret, and Passkey) are required to activate the integration.')
                return redirect('mpesa_settings')

        settings.is_active = is_active
        settings.save()

        messages.success(request, 'M-Pesa settings updated successfully!')
        return redirect('mpesa_settings')

    is_configured = settings.is_active and all([
        settings.consumer_key, settings.consumer_secret, settings.passkey
    ])

    context = {
        'settings': settings,
        'is_configured': is_configured
    }
    return render(request, 'api/mpesa_settings.html', context)

from django.views.decorators.csrf import csrf_exempt

@login_required
@csrf_exempt
def mpesa_save_money(request):
    """Handle M-Pesa STK push for saving money"""
    try:
        mpesa_settings = MpesaSettings.objects.get(user=request.user)
    except MpesaSettings.DoesNotExist:
        messages.error(request, 'Please configure your M-Pesa settings first.')
        return redirect('mpesa_settings')

    if not mpesa_settings.is_active:
        messages.error(request, 'M-Pesa integration is not active. Please activate it in settings.')
        return redirect('mpesa_settings')

    if not mpesa_settings.consumer_key or not mpesa_settings.consumer_secret or not mpesa_settings.passkey:
        messages.error(request, 'M-Pesa credentials are not configured. Please set your Consumer Key, Consumer Secret, and Passkey.')
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

        # Use MpesaService
        from .services import MpesaService
        mpesa_service = MpesaService(
            mpesa_settings.consumer_key,
            mpesa_settings.consumer_secret,
            mpesa_settings.shortcode,
            mpesa_settings.passkey,
            mpesa_settings.is_sandbox
        )

        # Initiate STK push
        result = mpesa_service.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f"Save-{request.user.username}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            transaction_desc=f"Save Money - {request.user.username}"
        )

        if 'error' not in result:
            # Create transaction record
            MpesaTransaction.objects.create(
                user=request.user,
                amount=amount,
                phone_number=phone_number,
                checkout_request_id=result.get('CheckoutRequestID'),
                merchant_request_id=result.get('MerchantRequestID'),
                response_code=result.get('ResponseCode'),
                response_description=result.get('CustomerMessage'),
                customer_message=result.get('CustomerMessage'),
                status='pending'
            )

            messages.success(request, f'STK push sent to {phone_number}. Please check your phone and enter your M-Pesa PIN.')
            return redirect('mpesa_transactions')
        else:
            # Parse M-Pesa API error for better user message
            error_msg = result["error"]
            if isinstance(error_msg, dict):
                error_code = error_msg.get('errorCode', 'Unknown')
                error_message = error_msg.get('errorMessage', 'Unknown error')
                if 'Wrong credentials' in error_message or error_code == '500.001.1001':
                    user_error = 'Invalid M-Pesa credentials. Please verify your Consumer Key and Consumer Secret in the M-Pesa settings page.'
                else:
                    user_error = f'M-Pesa API error ({error_code}): {error_message}. Please check your settings and try again.'
            else:
                user_error = f'Failed to initiate payment: {error_msg}. Please check your M-Pesa settings.'

            messages.error(request, user_error)
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

    if not settings.consumer_key or not settings.consumer_secret or not settings.passkey:
        messages.error(request, 'M-Pesa credentials are not configured. Please set your Consumer Key, Consumer Secret, and Passkey.')
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

@login_required
def mpesa_test_connection(request):
    """Test M-Pesa API connectivity"""
    try:
        settings = MpesaSettings.objects.get(user=request.user)
    except MpesaSettings.DoesNotExist:
        messages.error(request, 'Please configure your M-Pesa settings first.')
        return redirect('mpesa_settings')

    if not settings.is_active:
        messages.error(request, 'M-Pesa integration is not active. Please activate it in settings.')
        return redirect('mpesa_settings')

    if not settings.consumer_key or not settings.consumer_secret or not settings.passkey:
        messages.error(request, 'M-Pesa credentials are not configured. Please set your Consumer Key, Consumer Secret, and Passkey.')
        return redirect('mpesa_settings')

    from .services import MpesaService
    mpesa_service = MpesaService(
        settings.consumer_key,
        settings.consumer_secret,
        settings.shortcode,
        settings.passkey,
        settings.is_sandbox
    )

    result = mpesa_service.test_connection()

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['error'])

    return redirect('mpesa_settings')

@login_required
def mpesa_check_pending_transactions(request):
    """Check and update status of pending M-Pesa transactions"""
    try:
        settings = MpesaSettings.objects.get(user=request.user)
    except MpesaSettings.DoesNotExist:
        messages.error(request, 'Please configure your M-Pesa settings first.')
        return redirect('mpesa_transactions')

    if not settings.is_active:
        messages.error(request, 'M-Pesa integration is not active. Please activate it in settings.')
        return redirect('mpesa_transactions')

    from .services import MpesaService
    mpesa_service = MpesaService(
        settings.consumer_key,
        settings.consumer_secret,
        settings.shortcode,
        settings.passkey,
        settings.is_sandbox
    )

    # Check pending transactions
    pending_transactions = MpesaTransaction.objects.filter(
        user=request.user,
        status='pending'
    )

    updated_count = 0
    for transaction in pending_transactions:
        if transaction.checkout_request_id:
            result = mpesa_service.query_stk_push_status(transaction.checkout_request_id)
            if 'error' not in result:
                result_code = result.get('ResultCode', 1)
                if result_code == 0:
                    # Success
                    callback_metadata = result.get('CallbackMetadata', {})
                    items = callback_metadata.get('Item', [])
                    transaction.status = 'completed'
                    transaction.completed_at = datetime.now()
                    for item in items:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            transaction.mpesa_receipt_number = item.get('Value')
                        elif item.get('Name') == 'TransactionDate':
                            transaction.transaction_date = item.get('Value')
                    transaction.response_description = result.get('ResultDesc', 'Transaction completed')
                    transaction.save()
                    updated_count += 1
                    logger.info(f"Transaction {transaction.id} updated to completed")
                elif result_code != 0:
                    # Failed
                    transaction.status = 'failed'
                    transaction.response_description = result.get('ResultDesc', 'Transaction failed')
                    transaction.save()
                    updated_count += 1
                    logger.info(f"Transaction {transaction.id} updated to failed")

    # Check pending withdrawals
    pending_withdrawals = MpesaWithdrawal.objects.filter(
        user=request.user,
        status='pending'
    )

    for withdrawal in pending_withdrawals:
        if withdrawal.checkout_request_id:
            result = mpesa_service.query_b2c_status(withdrawal.checkout_request_id)
            if 'error' not in result:
                result_code = result.get('ResultCode', 1)
                if result_code == 0:
                    # Success
                    callback_metadata = result.get('CallbackMetadata', {})
                    items = callback_metadata.get('Item', [])
                    withdrawal.status = 'completed'
                    withdrawal.completed_at = datetime.now()
                    for item in items:
                        if item.get('Name') == 'TransactionId':
                            withdrawal.transaction_id = item.get('Value')
                        elif item.get('Name') == 'MpesaReceiptNumber':
                            withdrawal.mpesa_receipt_number = item.get('Value')
                    withdrawal.response_description = result.get('ResultDesc', 'Withdrawal completed')
                    withdrawal.save()
                    updated_count += 1
                    logger.info(f"Withdrawal {withdrawal.id} updated to completed")
                elif result_code != 0:
                    # Failed
                    withdrawal.status = 'failed'
                    withdrawal.response_description = result.get('ResultDesc', 'Withdrawal failed')
                    withdrawal.save()
                    updated_count += 1
                    logger.info(f"Withdrawal {withdrawal.id} updated to failed")

    if updated_count > 0:
        messages.success(request, f'Updated status for {updated_count} pending transaction(s).')
    else:
        messages.info(request, 'No pending transactions found or no updates available.')

    return redirect('mpesa_transactions')

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


