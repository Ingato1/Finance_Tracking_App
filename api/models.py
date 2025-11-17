from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from uuid import uuid4
import os

# Optional field-level encryption using Fernet. To enable, set env var MPESA_ENCRYPTION_KEY
try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    Fernet = None
    InvalidToken = Exception

class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, unique=True, blank=True)
    mpesa_api_token = models.TextField(blank=True)
    preferences = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username}"

class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=[('income', 'Income'), ('expense', 'Expense')])
    color = models.CharField(max_length=7, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=[('income', 'Income'), ('expense', 'Expense')])
    description = models.TextField(blank=True)
    transaction_date = models.DateField()
    mpesa_transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'transaction_date']),
            models.Index(fields=['mpesa_transaction_id']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"

class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default='Default Budget')
    period_type = models.CharField(max_length=20, choices=[('monthly', 'Monthly'), ('weekly', 'Weekly'), ('custom', 'Custom')], default='monthly')
    month = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.name}"

class BudgetCategories(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ['budget', 'category']

    def __str__(self):
        return f"{self.budget.name} - {self.category.name} - {self.allocated_amount}"

class SavingsGoals(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'target_date']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.name}"

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"

class MpesaSettings(models.Model):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shortcode = models.CharField(max_length=20, default='174379')
    passkey = models.CharField(max_length=100, blank=True)
    consumer_key = models.CharField(max_length=100, blank=True)
    consumer_secret = models.CharField(max_length=100, blank=True)
    is_sandbox = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_consumer_key(self):
        return self._maybe_decrypt(self.consumer_key)

    def get_consumer_secret(self):
        return self._maybe_decrypt(self.consumer_secret)

    def get_passkey(self):
        return self._maybe_decrypt(self.passkey)

    def encrypt_and_save(self):
        f = self._get_fernet()
        if not f:
            return self
        ck = self._maybe_decrypt(self.consumer_key)
        cs = self._maybe_decrypt(self.consumer_secret)
        pk = self._maybe_decrypt(self.passkey)
        self.consumer_key = self._maybe_encrypt(ck) if ck else ''
        self.consumer_secret = self._maybe_encrypt(cs) if cs else ''
        self.passkey = self._maybe_encrypt(pk) if pk else ''
        self.save()
        return self

    def _maybe_encrypt(self, value):
        f = self._get_fernet()
        if not f or not value:
            return value
        try:
            return f.encrypt(value.encode()).decode()
        except Exception:
            return value

    def _maybe_decrypt(self, value):
        f = self._get_fernet()
        if not f or not value:
            return value
        try:
            return f.decrypt(value.encode()).decode()
        except InvalidToken:
            return value
        except Exception:
            return value

    def _get_fernet(self):
        key = os.environ.get('MPESA_ENCRYPTION_KEY')
        if not key or not Fernet:
            return None
        try:
            return Fernet(key.encode())
        except Exception:
            return None

    def __str__(self):
        return f"M-Pesa Settings for {self.user.username}"

class MpesaTransaction(models.Model):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending')
    response_code = models.CharField(max_length=10, null=True, blank=True)
    response_description = models.TextField(null=True, blank=True)
    customer_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)
    transaction_id = models.CharField(max_length=50, unique=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"M-Pesa Transaction: {self.user.username} - {self.amount}"

class ExpenseCategory(models.Model):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def display_name(self):
        return self.name.replace('_', ' ').title()

    def __str__(self):
        return self.display_name()

class Expense(models.Model):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.CharField(max_length=200)
    date = models.DateField(default=timezone.now)
    frequency = models.CharField(max_length=10, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily')
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.description}"

class MpesaWithdrawal(models.Model):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    withdrawal_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending')
    response_code = models.CharField(max_length=10, null=True, blank=True)
    response_description = models.TextField(null=True, blank=True)
    customer_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal: {self.user.username} - {self.amount}"
