from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import Transaction, Budget, Category, UserProfile, SavingsGoals, Expense, ExpenseCategory
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
            # Create UserProfile automatically
            UserProfile.objects.create(user=user)
        return user

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'mpesa_api_token', 'preferences']
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254712345678'}),
            'mpesa_api_token': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'preferences': forms.HiddenInput(),
        }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove all non-digit characters
            cleaned = re.sub(r'\D', '', phone_number)
            # Check if it's a valid Kenyan number
            if len(cleaned) == 12 and cleaned.startswith('254'):
                return f"+{cleaned}"
            elif len(cleaned) == 9 and cleaned.startswith('7'):
                return f"+254{cleaned}"
            elif len(cleaned) == 10 and cleaned.startswith('07'):
                return f"+254{cleaned[1:]}"
            else:
                raise forms.ValidationError("Please enter a valid Kenyan phone number.")
        return phone_number

class SavingsGoalsForm(forms.ModelForm):
    class Meta:
        model = SavingsGoals
        fields = ['name', 'target_amount', 'target_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'target_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean_target_date(self):
        target_date = self.cleaned_data.get('target_date')
        if target_date and target_date <= datetime.now().date():
            raise forms.ValidationError("Target date must be in the future.")
        return target_date

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text="Enter the email address associated with your account."
    )

class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Your password must contain at least 8 characters."
    )
    new_password2 = forms.CharField(
        label="New password confirmation",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Enter the same password as before, for verification."
    )

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
    class Meta:
        model = Budget
        fields = ['name', 'period_type', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'period_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

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
