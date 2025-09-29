from django.test import TestCase
from django.contrib.auth.models import User
from .forms import CategoryForm
from .models import ExpenseCategory

class CategoryFormTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_custom_category_others_with_name(self):
        """Test creating custom category under 'others' with valid name"""
        form_data = {
            'name': 'others',
            'custom_name': 'Groceries',
            'description': 'Food shopping'
        }
        form = CategoryForm(data=form_data)
        self.assertTrue(form.is_valid())
        category = form.save()
        self.assertEqual(category.name, 'Groceries')
        self.assertEqual(category.description, 'Food shopping')

    def test_custom_category_others_without_name(self):
        """Test validation error when 'others' selected without custom name"""
        form_data = {
            'name': 'others',
            'custom_name': '',
            'description': 'Food shopping'
        }
        form = CategoryForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("Please specify a name for the 'Others' category.", form.non_field_errors())

    def test_regular_category_creation(self):
        """Test creating regular category without 'others'"""
        form_data = {
            'name': 'food',
            'custom_name': '',  # Should be ignored
            'description': 'Meals'
        }
        form = CategoryForm(data=form_data)
        self.assertTrue(form.is_valid())
        category = form.save()
        self.assertEqual(category.name, 'food')
        self.assertEqual(category.description, 'Meals')

    def test_custom_name_trimmed(self):
        """Test that custom_name is trimmed of whitespace"""
        form_data = {
            'name': 'others',
            'custom_name': '  Unique Groceries  ',
            'description': 'Food shopping'
        }
        form = CategoryForm(data=form_data)
        self.assertTrue(form.is_valid())
        category = form.save()
        self.assertEqual(category.name, 'Unique Groceries')  # Trimmed
