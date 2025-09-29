from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.utils import timezone
from datetime import date
from .models import Budget
from .forms import BudgetForm
from .views import set_budget, dashboard, spending_analysis
import json

class BudgetTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
        # Create a budget for current month
        current_month = timezone.now().replace(day=1)
        self.existing_budget = Budget.objects.create(
            user=self.user,
            amount=1000,
            month=current_month
        )
        
        # Create a budget for next month
        next_month = current_month.replace(month=current_month.month % 12 + 1)
        if next_month.month == 1:
            next_month = next_month.replace(year=next_month.year + 1)
        self.next_month = next_month

    def test_update_existing_budget(self):
        """Test updating an existing budget for the same month"""
        response = self.client.post('/api/set-budget/', {
            'month': self.existing_budget.month.strftime('%Y-%m'),
            'amount': '1500'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard
        budget = Budget.objects.get(user=self.user, month=self.existing_budget.month)
        self.assertEqual(budget.amount, 1500)
        self.assertEqual(budget.user, self.user)

    def test_create_new_budget(self):
        """Test creating a new budget for a different month"""
        response = self.client.post('/api/set-budget/', {
            'month': self.next_month.strftime('%Y-%m'),
            'amount': '2000'
        })
        
        self.assertEqual(response.status_code, 302)
        budget = Budget.objects.get(user=self.user, month=self.next_month)
        self.assertEqual(budget.amount, 2000)
        self.assertEqual(budget.user, self.user)

    def test_form_validation_empty_amount(self):
        """Test form validation for empty amount"""
        response = self.client.post('/api/set-budget/', {
            'month': self.next_month.strftime('%Y-%m'),
            'amount': ''  # Empty amount should fail validation
        })
        
        self.assertEqual(response.status_code, 200)  # Should render form with errors
        self.assertContains(response, 'This field is required.')
        # Verify no budget was created
        self.assertFalse(Budget.objects.filter(user=self.user, month=self.next_month).exists())

    def test_no_integrity_error_on_update(self):
        """Ensure no IntegrityError when updating existing budget"""
        # This tests the view logic indirectly by ensuring the update works without exception
        response = self.client.post('/api/set-budget/', {
            'month': self.existing_budget.month.strftime('%Y-%m'),
            'amount': '2500'
        })
        
        self.assertEqual(response.status_code, 302)
        # Verify the budget was updated
        updated_budget = Budget.objects.get(id=self.existing_budget.id)
        self.assertEqual(updated_budget.amount, 2500)

    def test_delete_budget(self):
        """Test budget deletion"""
        from django.urls import reverse
        
        budget_id = self.existing_budget.id
        response = self.client.post(reverse('delete_budget', args=[budget_id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Budget.objects.filter(id=budget_id).exists())

    def test_budget_in_dashboard(self):
        """Test that budget appears in dashboard context"""
        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('budget', response.context)
        self.assertEqual(response.context['budget'].amount, 1000)

    def test_budget_in_spending_analysis(self):
        """Test budget data in spending analysis"""
        response = self.client.get('/api/analysis/')
        self.assertEqual(response.status_code, 200)
        # Check if budget data is processed
        self.assertIn('budget_comparison_budget', response.context)
