# SaveWise Finance Tracker - System Design Documentation

## 4.5 Process Design

### 4.5.1 Use Case Diagram

```
[User] ------> (Register Account)
[User] ------> (Login)
[User] ------> (Connect M-Pesa)
[User] ------> (View Dashboard)
[User] ------> (Set Budget)
[User] ------> (Create Savings Goal)
[User] ------> (View Reports)
[User] ------> (Categorize Transactions)
[User] ------> (Receive Alerts)

[Admin] -----> (Manage Users)
[Admin] -----> (View System Analytics)
[Admin] -----> (Configure System)

[System] ----> (Sync M-Pesa Transactions)
[System] ----> (Categorize Automatically)
[System] ----> (Generate Alerts)
[System] ----> (Send Notifications)
```

### 4.5.2 Transaction Synchronization Flowchart

```
Start
  ↓
Authenticate with Daraja API
  ↓
Retrieve transaction list since last sync
  ↓
For each transaction:
  ↓
Check if transaction exists in local database
  ↓
If new transaction:
  ↓
Extract amount, date, description, party details
  ↓
Apply categorization rules
  ↓
Store transaction with auto-categorized flag
  ↓
Update spending analytics in real-time
  ↓
Check budget impacts and trigger alerts if needed
  ↓
Continue to next transaction
  ↓
Update last sync timestamp
  ↓
Log synchronization summary
  ↓
End
```

### 4.5.3 Data Flow Diagrams

**Level 0 DFD:**
```
[User] --> (Transaction Data) --> [SaveWise System] --> (Visualizations) --> [User]
[M-Pesa] --> (API Data) --> [SaveWise System] --> (Storage Requests) --> [Database]
[User] --> (Budget Settings) --> [SaveWise System] --> (Alert Triggers) --> [Notification System]
```

**Level 1 DFD - Transaction Processing:**
```
[M-Pesa API] --> (Raw Transaction Data) --> [Data Validation] --> (Validated Data) --> [Categorization Engine]
[Categorization Engine] --> (Categorized Transactions) --> [Spending Analytics] --> (Analytics Data) --> [Dashboard]
[Spending Analytics] --> (Budget Comparison) --> [Alert System] --> (Notifications) --> [User Interface]
```

### 4.5.4 System Architecture Diagram

The system follows a three-tier architecture:

**Presentation Layer:**
- Django Templates with responsive HTML5/CSS3
- Chart.js for interactive visualizations
- JavaScript for dynamic content updates
- Bootstrap framework for consistent styling

**Application Layer:**
- Django MVC framework handling business logic
- RESTful API for mobile client support
- Background task processing via Celery
- Authentication and authorization middleware

**Data Layer:**
- PostgreSQL database for structured data
- Redis for caching and session storage
- Secure file storage for documents and exports
- Encrypted backup systems

## 4.6 Database Design

### 4.6.1 Entity Relationship Diagram

```
[User] (1) ---- (M) [Transaction]
  |                   |
  |                   |
  |                  (M)
  |                   |
(M)                 [Category]
  |                   |
[Budget] (1) ---- (M) [BudgetCategory]
  |                   |
  |                  (M)
  |                   |
(M)                 [SavingsGoal]
  |                   |
[Alert] (M) ---- (1) [User]
```

### 4.6.2 Database Schema

#### UserProfile Table
- user_id (FK to User, unique)
- phone_number (varchar)
- date_of_birth (date)
- currency (varchar, default 'KES')
- monthly_income (decimal)
- savings_goal_percentage (decimal, default 20.00)
- email_notifications (boolean, default true)
- sms_notifications (boolean, default false)
- budget_alerts (boolean, default true)
- spending_alerts (boolean, default true)
- notification_frequency (varchar, choices)
- profile_visibility (boolean, default true)
- created_at (datetime)
- updated_at (datetime)

#### SavingsGoal Table
- id (PK)
- user_id (FK to User)
- name (varchar)
- description (text)
- target_amount (decimal)
- current_amount (decimal, default 0)
- target_date (date)
- status (varchar, choices: active/completed/paused/cancelled)
- created_at (datetime)
- updated_at (datetime)

#### Notification Table
- id (PK)
- user_id (FK to User)
- title (varchar)
- message (text)
- notification_type (varchar, choices)
- delivery_method (varchar, choices: email/sms/in_app)
- is_read (boolean, default false)
- is_sent (boolean, default false)
- sent_at (datetime, nullable)
- created_at (datetime)

#### Expense Table (Enhanced)
- id (PK)
- user_id (FK to User)
- amount (decimal)
- description (varchar)
- category_id (FK to ExpenseCategory, nullable)
- date (date)
- frequency (varchar, choices)
- created_at (datetime)
- Indexes: (user, date), (user, category)

#### Budget Table (Enhanced)
- id (PK)
- user_id (FK to User)
- amount (decimal)
- month (date, first day of month)
- created_at (datetime)
- Unique constraint: (user, month)

#### MpesaTransaction Table (Enhanced)
- id (PK)
- user_id (FK to User)
- amount (decimal)
- phone_number (varchar)
- transaction_id (varchar, unique, nullable)
- checkout_request_id (varchar, unique, nullable)
- merchant_request_id (varchar, nullable)
- status (varchar, choices)
- response_code (varchar, nullable)
- response_description (text, nullable)
- customer_message (text, nullable)
- created_at (datetime)
- completed_at (datetime, nullable)
- mpesa_receipt_number (varchar, nullable)
- Indexes: (user, status), (user, created_at)

### 4.6.3 Data Integrity Constraints

- All foreign key relationships with CASCADE delete where appropriate
- Unique constraints on user-specific data (budgets per month, transaction IDs)
- Validation rules for amounts (positive values), dates (future dates for goals)
- Phone number format validation for Kenyan numbers
- Email uniqueness across users

### 4.6.4 Indexing Strategy

- Composite indexes on frequently queried fields (user + date, user + category)
- Partial indexes for active records
- Foreign key indexes for performance
- Full-text search indexes for transaction descriptions

### 4.6.5 Backup and Recovery

- Daily automated backups with encryption
- Point-in-time recovery capability
- Off-site backup storage
- Backup verification procedures
- Disaster recovery plan with RTO/RPO metrics
