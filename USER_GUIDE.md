# QA Test Generator v2.1 - User Guide

## Overview

QA Test Generator is an AI-powered automated testing solution designed for Odoo ERP implementation providers. It enables you to manage QA testing across multiple customers from a single hub, with a focus on:

1. **Code-First Testing** - Scan Git repos, auto-generate tests from source code
2. **Requirement Validation** - Prove customer requirements are met
3. **Regression Testing** - Ensure changes don't break existing workflows
4. **Health Monitoring** - Monitor integrations, data integrity, and system health

### Key Features

- **Code-First Test Generation** - Point at Git repo, AI generates tests from code ⭐ NEW
- **Multi-Customer Management** - Manage tests for unlimited customers
- **Requirement-Driven Testing** - Link tests directly to customer requirements
- **AI-Powered Test Generation** - Claude AI generates Robot Framework tests
- **Pre-Built Regression Templates** - Ready-to-use tests for standard Odoo modules
- **Health Monitoring** - Track integrations, data integrity, Studio changes, cron jobs
- **Git Integration** - Fetch source code from GitHub/GitLab/Bitbucket
- **Jenkins CI/CD** - Automated pipeline support

---

## Table of Contents

1. [Installation](#1-installation)
2. [Initial Configuration](#2-initial-configuration)
3. [Managing Customers](#3-managing-customers)
4. [Code Scanning & Test Generation](#4-code-scanning--test-generation) ⭐ NEW
5. [Requirements Management](#5-requirements-management)
6. [Health Monitoring](#6-health-monitoring)
7. [Regression Testing](#7-regression-testing)
8. [Test Specifications](#8-test-specifications)
9. [Running Tests](#9-running-tests)
10. [Best Practices](#10-best-practices)

---

## 1. Installation

### Requirements

- Odoo 18.0 Community or Enterprise
- Python packages: `anthropic`, `requests`
- Git (for code scanning)
- Robot Framework (on test execution server)

### Install Steps

```bash
# 1. Extract module to addons folder
cd /opt/odoo18/custom_addons
unzip qa_test_generator.zip

# 2. Install Python dependencies
pip install anthropic requests

# 3. Restart Odoo
sudo systemctl restart odoo

# 4. Update Apps List
# Go to Apps → Update Apps List

# 5. Install Module
# Search "qa_test_generator" → Install
```

---

## 2. Initial Configuration

### 2.1 AI Settings

Navigate to: **QA Testing → Configuration → AI Settings**

| Field | Description | Example |
|-------|-------------|---------|
| Name | Configuration name | `Production AI Config` |
| AI Provider | Select AI provider | `Anthropic (Claude)` |
| API Key | Your API key | `sk-ant-api03-xxx...` |
| Model | AI model to use | `claude-sonnet-4-20250514` |
| Max Tokens | Maximum response length | `4000` |

Click **Test Connection** to verify.

### 2.2 Jenkins Integration (Optional)

| Field | Description |
|-------|-------------|
| Jenkins Enabled | Enable CI/CD integration |
| Jenkins URL | `https://jenkins.mycompany.com` |
| Jenkins User | Jenkins username |
| Jenkins Token | API token |
| Job Name | Jenkins job for running tests |

---

## 3. Managing Customers

Navigate to: **QA Testing → Customers**

### 3.1 Create Customer

| Field | Description | Example |
|-------|-------------|---------|
| Customer Name | Company name | `ACME Corporation` |
| Code | Short identifier | `ACME` |
| Odoo Version | Customer's Odoo version | `18.0` |
| Account Manager | Responsible user | `Your name` |
| Contact Name | Primary contact | `John Smith` |
| Contact Email | Email address | `john@acme.com` |

### 3.2 Add Git Repository

Navigate to: **QA Testing → Configuration → Git Repositories → New**

| Field | Description | Example |
|-------|-------------|---------|
| Name | Repository name | `ACME Custom Modules` |
| Customer | Select customer | `ACME Corporation` |
| Provider | Git provider | `GitHub` |
| Repository URL | Full HTTPS URL | `https://github.com/acme/odoo-modules` |
| Default Branch | Main branch | `main` |
| Authentication | Auth type | `Personal Access Token` |
| Access Token | PAT with repo scope | `ghp_xxx...` |

### 3.3 Add Test Server

In the **Servers** tab, add customer's Odoo environments:

| Field | Description | Example |
|-------|-------------|---------|
| Server Name | Descriptive name | `ACME Staging` |
| Environment | Server type | `Staging` |
| Odoo URL | Base URL | `https://acme-staging.odoo.com` |
| Database | Database name | `acme_staging` |
| Auth Type | Authentication method | `API Key` |
| API Key | Odoo API key | `xxx...` |

---

## 4. Code Scanning & Test Generation ⭐ NEW

The fastest way to get tests - point at source code and let AI do the work!

### 4.1 Quick Start

1. **From Customer form**, click **🔍 Scan & Generate Tests**
2. Or navigate to: **QA Testing → Code Scanning → Scan & Generate**

### 4.2 Scan Workflow

```
Step 1: Select Repository & Branch
    ↓
Step 2: Scan → Discovers Odoo modules
    ↓
Step 3: Select modules to analyze
    ↓
Step 4: Analyze → AI reads code structure
    ↓
Step 5: Generate → Creates test cases
    ↓
Step 6: Run tests against server
```

### 4.3 What Gets Analyzed

For each module, the scanner extracts:

**From Python Files:**
- Model definitions (`_name`, `_inherit`)
- Field definitions (type, required, computed)
- Constraints (`@api.constrains`, `_sql_constraints`)
- Button actions (`action_*`, `button_*` methods)
- Workflow states and transitions
- Override methods (`create`, `write`, `unlink`)

**From XML Files:**
- Form and list views
- Button definitions
- Required field markers
- Menu items and actions

### 4.4 Generated Test Categories

| Category | What It Tests |
|----------|---------------|
| CRUD | Create, Read, Update, Delete operations |
| Validation | Required fields, constraints |
| Workflow | State transitions, action methods |
| Computation | Computed field results |
| Security | Access rights (if configured) |
| Negative | Error handling, edge cases |

### 4.5 Generation Options

Before generating, you can customize:

| Option | Default | Description |
|--------|---------|-------------|
| Include CRUD Tests | ✓ | Basic data operations |
| Include Validation Tests | ✓ | Required fields, constraints |
| Include Workflow Tests | ✓ | State transitions |
| Include Security Tests | ✓ | Access control |
| Include Negative Tests | ✓ | Error scenarios |
| Max Tests per Model | 25 | Limit test count |

### 4.6 Example Output

For a model with:
- 5 required fields
- 3 state transitions
- 2 constraints
- 4 button actions

AI typically generates:
- 4 CRUD tests
- 5 validation tests (one per required field)
- 3 workflow tests (one per transition)
- 2 constraint tests
- 4 action tests
- ~5 negative tests

**Total: ~23 tests automatically!**

---

## 5. Requirements Management

Navigate to: **QA Testing → Requirements**

### 4.1 What Are Requirements?

Requirements link customer requests to acceptance tests. Instead of writing abstract test specs, you:

1. Document what the customer needs
2. Define acceptance criteria
3. Generate tests that prove the requirement is met

### 4.2 Create Requirement

Click **New** and fill in:

| Field | Description | Example |
|-------|-------------|---------|
| Code | Unique identifier | `REQ-001` |
| Name | Requirement title | `Multi-warehouse stock transfers` |
| Customer | Select customer | `ACME Corporation` |
| Category | Type of requirement | `Feature` |
| Priority | Importance level | `High` |

### 4.3 Write Description

In the **Description** tab, explain what the customer needs:

```
The customer needs to transfer stock between their 3 warehouses:
- Main Warehouse (Sydney)
- Distribution Center (Melbourne)  
- Retail Store (Brisbane)

Users should be able to:
1. Create transfer requests from any warehouse
2. See available stock at source warehouse
3. Track transfers in transit
4. Receive transfers at destination
```

### 4.4 Define Acceptance Criteria

In the **Acceptance Criteria** tab, define how you'll know it works:

```
✓ User can create internal transfer from Warehouse A to Warehouse B
✓ System shows available quantity at source warehouse
✓ Transfer reduces source stock when confirmed
✓ Transfer increases destination stock when received
✓ Transfer history is visible on product form
✓ User cannot transfer more than available quantity
```

### 4.5 Generate Acceptance Tests

Click **Generate Tests** to have AI create test cases based on your requirements and acceptance criteria.

### 4.6 Requirement Workflow

```
Draft → Approved → Implementing → Testing → Deployed → Verified
```

| State | Description |
|-------|-------------|
| Draft | Initial documentation |
| Approved | Customer approved scope |
| Implementing | Development in progress |
| Testing | Tests being run |
| Deployed | Feature deployed to customer |
| Verified | Tests passed, requirement met |

### 4.7 Verify Requirements

When all acceptance tests pass, click **Mark Verified** to confirm the requirement is met.

---

## 5. Health Monitoring ⭐ NEW

Navigate to: **QA Testing → Monitoring → Health Checks**

### 5.1 What Are Health Checks?

Health checks automatically monitor:
- **Integrations** - API endpoints, EDI, payment gateways
- **Data Integrity** - Orphaned records, broken links, imbalances
- **Studio Changes** - Detect field/view modifications
- **Cron Jobs** - Ensure scheduled tasks are running
- **Performance** - Query response times

### 5.2 Create Integration Check

Monitor an external API:

| Field | Value |
|-------|-------|
| Name | `Payment Gateway API` |
| Customer | `ACME Corporation` |
| Check Type | `Integration/API` |
| Endpoint URL | `https://api.payment.com/health` |
| HTTP Method | `GET` |
| Expected Status | `200` |
| Timeout | `30` seconds |
| Check Interval | `Every 15 minutes` |

### 5.3 Create Data Integrity Check

Find orphaned records or imbalances:

| Field | Value |
|-------|-------|
| Name | `Orphan Stock Moves` |
| Check Type | `Data Integrity` |
| Check Query | `[('product_id', '=', False), ('state', '=', 'done')]` |
| Model | `stock.move` |
| Expected Result | `Zero records` |

Example SQL check for accounting balance:
```sql
SELECT ABS(SUM(debit) - SUM(credit)) as imbalance 
FROM account_move_line 
WHERE parent_state = 'posted'
HAVING ABS(SUM(debit) - SUM(credit)) > 0.01
```

### 5.4 Create Studio Change Detection

Detect when someone modifies fields via Odoo Studio:

| Field | Value |
|-------|-------|
| Name | `Sale Order Field Monitor` |
| Check Type | `Studio Change Detection` |
| Model to Watch | `sale.order` |

Click **Run Check** to capture the baseline. Future checks will alert if fields are added, removed, or modified.

### 5.5 Create Cron Job Monitor

Ensure scheduled jobs are running:

| Field | Value |
|-------|-------|
| Name | `Email Queue Processing` |
| Check Type | `Cron Job` |
| Cron Job | `Mail: Email Queue Manager` |
| Max Age (hours) | `1` |

Alert triggers if the cron hasn't run within the specified hours.

### 5.6 Alert Configuration

| Field | Description |
|-------|-------------|
| Alert on Failure | Send email on check failure |
| Alert After | Number of consecutive failures before alerting |
| Alert Email | Email address for notifications |

### 5.7 Check Statuses

| Status | Meaning |
|--------|---------|
| 🟢 OK | Check passed |
| 🟡 Warning | Potential issue |
| 🔴 Critical | Check failed |
| ⚪ Unknown | Not yet run |

---

## 6. Regression Testing ⭐ NEW

Navigate to: **QA Testing → Regression Testing**

### 6.1 What Are Regression Suites?

Regression suites contain pre-built tests for standard Odoo modules. Run them after any change to ensure nothing broke.

### 6.2 Pre-Built Templates

Available templates for:

| Module | Tests Included |
|--------|---------------|
| Sales | Create quotation, confirm order, create invoice |
| Purchase | Create PO, confirm, receive products |
| Inventory | Internal transfers, adjustments |
| Accounting | Create invoice, register payment |
| CRM | Lead to opportunity conversion |
| Data Integrity | Orphan records, balance checks |

### 6.3 Create Regression Suite

1. Navigate to **Regression Suites**
2. Click **New**
3. Select Customer
4. Choose Modules (e.g., `sale,purchase,stock,account`)
5. Click **Generate Tests**

### 6.4 Run Regression Suite

After any code change, config change, or upgrade:

1. Open the Regression Suite
2. Click **Run Suite**
3. Select target server
4. Review results

### 6.5 Pass Rate Tracking

Each suite tracks:
- Last run date
- Last run result (Pass/Fail)
- Overall pass rate percentage

---

## 7. Test Specifications

Navigate to: **QA Testing → Test Management → Test Specifications**

### 7.1 Create Specification

| Field | Description |
|-------|-------------|
| Specification Name | Descriptive title |
| Customer | Select customer |
| Odoo Module | Module being tested |
| Category | Test type |
| Test Suite | Group into suite |

### 7.2 Write Specification

In plain text, describe what to test:

```
Test Sale Order Workflow

PRECONDITIONS:
- User logged in as Sales Manager
- Product "Office Chair" exists with price $150
- Customer "Azure Interior" exists

TEST SCENARIOS:

1. Create Quotation
   - Navigate to Sales > Quotations
   - Click Create
   - Select customer "Azure Interior"
   - Add product "Office Chair" qty 2
   - Verify subtotal = $300

2. Confirm Order
   - Click Confirm
   - Verify state = "Sales Order"
   - Verify SO number starts with "S"
```

### 7.3 Generate Tests

Click **Generate Tests** to create Robot Framework test cases.

---

## 8. Running Tests

### 8.1 Run Options

| Method | Use Case |
|--------|----------|
| Single Test | Debug specific test |
| Test Suite | Run grouped tests |
| Regression Suite | Post-change validation |
| Customer: Run All | Full customer validation |

### 8.2 Execution Settings

| Setting | Description |
|---------|-------------|
| Target Server | Customer's server to test against |
| Include Tags | Only run tests with these tags |
| Exclude Tags | Skip tests with these tags |

### 8.3 Scheduled Runs

1. Open Test Suite
2. Enable **Scheduled**
3. Set interval (Daily/Weekly)
4. Set execution time

---

## 9. Viewing Results

Navigate to: **QA Testing → Execution → Test Runs**

### 9.1 Test Run Summary

| Metric | Description |
|--------|-------------|
| Total Tests | Tests executed |
| Passed | ✅ Successful tests |
| Failed | ❌ Failed tests |
| Errors | ⚠️ Tests with errors |
| Pass Rate | Success percentage |
| Duration | Total time |

### 9.2 Detailed Results

Click a test result to see:
- Step-by-step log
- Screenshots (on failure)
- Error messages
- Execution time

### 9.3 Health Check History

View trends over time for each health check in **Monitoring → Health Checks → [Check] → History**

---

## 10. Best Practices

### 10.1 Requirement-First Approach

```
1. Customer Request → Document as Requirement
2. Define Acceptance Criteria → Clear pass/fail conditions
3. Generate Tests → AI creates from criteria
4. Run Tests → Validate implementation
5. Mark Verified → Prove requirement met
```

### 10.2 Layered Testing Strategy

```
Layer 1: Health Checks (Automated, Every 15 min)
├── Integration APIs up?
├── Data integrity OK?
└── Crons running?

Layer 2: Smoke Tests (After each deployment)
├── Login works?
├── Key menus accessible?
└── Critical workflows complete?

Layer 3: Regression Tests (Weekly or after changes)
├── Sales workflow
├── Purchase workflow
├── Inventory operations
└── Accounting entries

Layer 4: Acceptance Tests (Per requirement)
├── REQ-001: Custom feature A
├── REQ-002: Integration B
└── REQ-003: Report C
```

### 10.3 Health Check Coverage

| Category | What to Monitor |
|----------|-----------------|
| Integrations | Payment gateways, shipping APIs, EDI endpoints |
| Data | Orphan records, sequence gaps, balance mismatches |
| Studio | Customer-modified fields/views |
| Crons | Email queue, scheduled reports, sync jobs |
| Performance | Key query response times |

### 10.4 When to Run What

| Event | Action |
|-------|--------|
| Deployment | Smoke tests + Regression suite |
| Config change | Affected module regression |
| Customer reports bug | Create test case, add to suite |
| Weekly | Full regression + Health check review |
| Monthly | All customer health reports |

---

## Quick Reference

### Menu Structure

```
QA Testing
├── Customers                → Manage clients
├── Requirements             → Customer requirements
├── Code Scanning            → ⭐ NEW
│   ├── Scan & Generate      → Scan repos, generate tests
│   └── Model Analyses       → View discovered models
├── Dashboard                → Overview
├── Test Management
│   ├── Test Specifications  → Write test specs
│   ├── Test Suites          → Group tests
│   └── Test Cases           → View/edit tests
├── Regression Testing
│   ├── Regression Suites    → Per-customer suites
│   └── Test Templates       → Pre-built templates
├── Execution
│   ├── Test Runs            → Execution history
│   └── Test Results         → Detailed results
├── Monitoring
│   └── Health Checks        → System monitoring
└── Configuration
    ├── AI Settings          → API configuration
    ├── Git Repositories     → Source repos
    └── All Servers          → Customer servers
```

### Status Colors

| Color | Meaning |
|-------|---------|
| 🟢 Green | Passed / OK / Verified |
| 🔴 Red | Failed / Critical / Error |
| 🟡 Yellow | Warning / Running |
| 🔵 Blue | Ready / Info / Implementing |
| ⚪ Gray | Draft / Unknown / Pending |

### Requirement States

| State | Color | Description |
|-------|-------|-------------|
| Draft | Gray | Being documented |
| Approved | Blue | Customer approved |
| Implementing | Yellow | In development |
| Testing | Blue | Running tests |
| Deployed | Green | Live on customer |
| Verified | Green | Tests passed |

### Health Check Types

| Type | Icon | Purpose |
|------|------|---------|
| Integration | 🔌 | API endpoint monitoring |
| Data Integrity | 🗃️ | Database checks |
| Studio Change | 🎨 | Field modification detection |
| Cron Job | ⏰ | Scheduled task monitoring |
| Performance | 📊 | Query timing |
| Custom | 🔧 | Custom Python checks |

---

## Troubleshooting

### Tests Won't Generate

- Check AI Settings → Test Connection
- Verify API key is valid
- Check module analysis completed

### Health Check Failing

- Verify endpoint URL is correct
- Check authentication headers
- Review error message in Last Message field

### Regression Tests Missing

- Verify templates exist for selected modules
- Check customer has required modules installed

---

## Support

For issues or feature requests, contact your Odoo implementation partner.

**Version:** 18.0.2.1.0
**Last Updated:** January 2026
