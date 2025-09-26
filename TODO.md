# Performance Optimization Tasks

## Step 1: Add Database Indexes
- [x] Add indexes to Expense model: (user, date), (user, category)
- [x] Add indexes to Budget model: (user, month)
- [x] Add indexes to MpesaTransaction model: (user, status), (user, created_at)
- [x] Add indexes to MpesaWithdrawal model: (user, status), (user, created_at)

## Step 2: Run Migrations
- [x] Run makemigrations to create migration for indexes
- [x] Run migrate to apply indexes

## Step 3: Optimize Queries in Views
- [x] Optimize dashboard view: add select_related for category in expenses
- [x] Optimize spending_analysis view: combine queries, add select_related/prefetch_related
- [x] Optimize expense_list view: add select_related
- [x] Optimize mpesa_transactions and mpesa_withdrawals: ensure efficient queries

## Step 4: Add Timeouts to M-Pesa API Calls
- [x] Add request timeouts to M-Pesa API calls in services.py

## Step 5: Test Response Times
- [x] Test response times for dashboard, spending_analysis, M-Pesa features, login/register

## Step 6: Add Pending Transaction Check Feature
- [x] Add view to check and update status of pending M-Pesa transactions
- [x] Add URL for the check pending transactions view
- [x] Add button in transactions template to trigger pending check
- [x] Test the pending transaction check functionality
