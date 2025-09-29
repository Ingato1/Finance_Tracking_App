from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Expense, Budget, ExpenseCategory
from datetime import datetime
import re

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Your password must contain at least 8 characters."
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Enter the same password as before, for verification."
    )
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['amount', 'description', 'category', 'date', 'frequency']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
        }

class BudgetForm(forms.ModelForm):
    month = forms.CharField(
        widget=forms.TextInput(attrs={
            'type': 'month',
            'class': 'form-control'
        })
    )

    class Meta:
        model = Budget
        fields = ['amount', 'month']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean_month(self):
        month = self.cleaned_data.get('month')
        print(f"DEBUG: clean_month received: {month} (type: {type(month)})")
        
        if not month:
            return month
            
        # If it's a string (from HTML5 input), convert it to date
        if isinstance(month, str):
            try:
                # Handle YYYY-MM format from HTML5 month input
                if re.match(r'^\d{4}-\d{2}$', month):
                    year, month_num = map(int, month.split('-'))
                    if 1 <= month_num <= 12:
                        return datetime(year, month_num, 1).date()
                    else:
                        raise forms.ValidationError("Month must be between 01 and 12.")
                else:
                    raise forms.ValidationError("Please use YYYY-MM format (e.g., 2025-05).")
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Conversion error: {e}")
                raise forms.ValidationError("Enter a valid date in YYYY-MM format.")
        
        # If it's already a date object, ensure it's the first day of month
        elif hasattr(month, 'replace'):
            return month.replace(day=1)
        
        return month

class CategoryForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('', '---------'),
        ('food', 'Food'),
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('clothes', 'Clothes'),
        ('transport', 'Transport'),
        ('others', 'Others'),
    ]

    name = forms.CharField(
        required=True,
        widget=forms.Select(choices=CATEGORY_CHOICES, attrs={'class': 'form-control', 'id': 'category-select'})
    )
    custom_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'custom-name',
            'placeholder': 'Enter custom category name',
            'style': 'display: none;'
        })
    )

    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        custom_name = cleaned_data.get('custom_name')
        
        if name == 'others':
            if not custom_name or custom_name.strip() == '':
                raise forms.ValidationError("Please specify a name for the 'Others' category.")
            cleaned_data['name'] = custom_name.strip()
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = self.cleaned_data['name']
        if commit:
            instance.save()
        return instance
