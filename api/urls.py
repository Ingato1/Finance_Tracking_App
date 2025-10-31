from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Main application URLs
    path('test-db/', views.test_db, name='test_db'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add-expense/', views.add_expense, name='add_expense'),
    path('set-budget/', views.set_budget, name='set_budget'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/edit/<int:expense_id>/', views.edit_expense, name='edit_expense'),
    path('expenses/delete/<int:expense_id>/', views.delete_expense, name='delete_expense'),
    path('analysis/', views.spending_analysis, name='spending_analysis'),
    path('charts-data/', views.expense_charts_data, name='expense_charts_data'),
    path('categories/', views.manage_categories, name='manage_categories'),
    path('categories/delete/<int:category_id>/', views.delete_category, name='delete_category'),
    path('budget/delete/<int:budget_id>/', views.delete_budget, name='delete_budget'),

    # M-Pesa Integration URLs
    path('mpesa/settings/', views.mpesa_settings, name='mpesa_settings'),
    path('mpesa/save-money/', views.mpesa_save_money, name='mpesa_save_money'),
    path('mpesa/transactions/', views.mpesa_transactions, name='mpesa_transactions'),
    path('mpesa/check-pending/', views.mpesa_check_pending_transactions, name='mpesa_check_pending'),
    path('mpesa/withdraw-money/', views.mpesa_withdraw_money, name='mpesa_withdraw_money'),
    path('mpesa/withdrawals/', views.mpesa_withdrawals, name='mpesa_withdrawals'),
    path('mpesa/test-connection/', views.mpesa_test_connection, name='mpesa_test_connection'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('mpesa/b2c-callback/', views.mpesa_b2c_callback, name='mpesa_b2c_callback'),
    path('mpesa/b2c-result/', views.mpesa_b2c_result, name='mpesa_b2c_result'),
    path('mpesa/b2c-timeout/', views.mpesa_b2c_timeout, name='mpesa_b2c_timeout'),
]
