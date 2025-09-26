from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone

class ExpenseCategory(models.Model):
    PREDEFINED_CATEGORIES = [
        ('food', 'Food'),
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('clothes', 'Clothes'),
        ('transport', 'Transport'),
        ('others', 'Others'),
    ]
    
    name = models.CharField(max_length=100, choices=PREDEFINED_CATEGORIES)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.get_name_display()
    
    def display_name(self):
        return self.get_name_display()

class Expense(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.CharField(max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'category']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.description}"

class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.DateField()  # Store as first day of the month
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'month']
    
    def __str__(self):
        return f"{self.user.username} - {self.month.strftime('%B %Y')}"  # Format: "May 2025"
    
    def save(self, *args, **kwargs):
        # Ensure month is always the first day of the month
        if self.month:
            self.month = self.month.replace(day=1)
        super().save(*args, **kwargs)
    
    def get_month_year(self):
        """Return month and year as separate values"""
        return self.month.month, self.month.year
    
    def get_month_name(self):
        """Return the month name (e.g., 'May')"""
        return self.month.strftime('%B')
    
    def get_year(self):
        """Return the year (e.g., 2025)"""
        return self.month.year
    
    def get_formatted_month(self):
        """Return formatted string (e.g., '05/2025')"""
        return self.month.strftime('%m/%Y')
    def get_iso_month(self):
        """Return ISO format (e.g., '2025-05') for HTML5 inputs"""
        return self.month.strftime('%Y-%m')

class MpesaTransaction(models.Model):
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    transaction_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='pending')
    response_code = models.CharField(max_length=10, null=True, blank=True)
    response_description = models.TextField(null=True, blank=True)
    customer_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - KSH {self.amount} - {self.status}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'created_at']),
        ]
        
class MpesaSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shortcode = models.CharField(max_length=20, default='174379')  # Default M-Pesa shortcode
    passkey = models.CharField(max_length=100, blank=True)
    consumer_key = models.CharField(max_length=100, blank=True)
    consumer_secret = models.CharField(max_length=100, blank=True)
    is_sandbox = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"M-Pesa Settings for {self.user.username}"

class MpesaWithdrawal(models.Model):
    WITHDRAWAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    withdrawal_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=WITHDRAWAL_STATUS_CHOICES, default='pending')
    response_code = models.CharField(max_length=10, null=True, blank=True)
    response_description = models.TextField(null=True, blank=True)
    customer_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Withdrawal: {self.user.username} - KSH {self.amount} - {self.status}"

    class Meta:
        ordering = ['-created_at']
