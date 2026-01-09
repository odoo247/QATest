# QA Test Generator - User Guide

## Overview

QA Test Generator is an AI-powered automated testing solution for Odoo ERP implementations. It enables ERP solution providers to manage QA testing across multiple customers from a single hub.

### Key Features

- **Multi-Customer Management** - Manage tests for unlimited customers
- **AI-Powered Test Generation** - Claude AI generates Robot Framework tests from plain text
- **Git Integration** - Fetch source code from GitHub/GitLab/Bitbucket
- **Multi-Server Support** - Test across dev/staging/UAT/production environments
- **Jenkins Integration** - CI/CD pipeline support
- **Pass Rate Tracking** - Per-customer and per-suite analytics

---

## Table of Contents

1. [Installation](#1-installation)
2. [Initial Configuration](#2-initial-configuration)
3. [Managing Customers](#3-managing-customers)
4. [Git Repository Setup](#4-git-repository-setup)
5. [Writing Test Specifications](#5-writing-test-specifications)
6. [Generating Tests](#6-generating-tests)
7. [Running Tests](#7-running-tests)
8. [Viewing Results](#8-viewing-results)
9. [Best Practices](#9-best-practices)

---

## 1. Installation

### Requirements

- Odoo 18.0 Community or Enterprise
- Python packages: `anthropic`, `requests`
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
# Search "QA Test Generator" → Install
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
| Test Base URL | Default Odoo URL for testing | `https://staging.mycompany.com` |

**Optional - Jenkins Integration:**

| Field | Description |
|-------|-------------|
| Jenkins Enabled | Enable CI/CD integration |
| Jenkins URL | `https://jenkins.mycompany.com` |
| Jenkins User | Jenkins username |
| Jenkins Token | API token |
| Job Name | Jenkins job for running tests |

Click **Test Connection** to verify AI API connectivity.

---

## 3. Managing Customers

Navigate to: **QA Testing → Customers**

### 3.1 Create Customer

Click **New** and fill in:

| Field | Description | Example |
|-------|-------------|---------|
| Customer Name | Company name | `ACME Corporation` |
| Code | Short identifier | `ACME` |
| Odoo Version | Customer's Odoo version | `18.0` |
| Contact Name | Primary contact | `John Smith` |
| Contact Email | Email address | `john@acme.com` |

### 3.2 Add Servers

In the **Servers** tab, add customer's Odoo environments:

| Field | Description | Example |
|-------|-------------|---------|
| Server Name | Descriptive name | `ACME Staging` |
| Environment | Server type | `Staging` |
| Odoo URL | Base URL | `https://acme-staging.odoo.com` |
| Database | Database name | `acme_staging` |
| Auth Type | Authentication method | `API Key` |
| API Key | Odoo API key | `xxx...` |

**For Robot Framework execution via SSH:**

| Field | Description |
|-------|-------------|
| SSH Enabled | Enable SSH connection |
| SSH Host | Server hostname/IP |
| SSH Port | SSH port (default: 22) |
| SSH User | SSH username |
| SSH Private Key | Private key content |
| Robot Path | Path to Robot Framework |

Click **Test Connection** to verify.

### 3.3 Customer Dashboard

Each customer card shows:
- Number of servers, specs, and test suites
- Overall pass rate
- Last test run status and date

---

## 4. Git Repository Setup

Navigate to: **QA Testing → Configuration → Git Repositories**

### 4.1 Add Repository

| Field | Description | Example |
|-------|-------------|---------|
| Name | Repository name | `ACME Custom Modules` |
| Customer | Select customer | `ACME Corporation` |
| Provider | Git provider | `GitHub` |
| Repository URL | Full URL | `https://github.com/acme/odoo-modules` |
| Default Branch | Main branch | `main` |
| Authentication | Auth type | `Personal Access Token` |
| Access Token | PAT with repo access | `ghp_xxx...` |

### 4.2 Link Module Sources

Navigate to: **QA Testing → Configuration → Module Sources**

Link customer's installed Odoo modules to their Git repository:

| Field | Description |
|-------|-------------|
| Module | Select installed module |
| Repository | Select Git repository |
| Branch | Branch override (optional) |
| Module Path | Path in repo (e.g., `addons/sale_custom`) |

---

## 5. Writing Test Specifications

Navigate to: **QA Testing → Test Management → Test Specifications**

### 5.1 Create Specification

Click **New** and fill in:

| Field | Description |
|-------|-------------|
| Specification Name | Descriptive title |
| Customer | Select customer |
| Odoo Module | Module being tested |
| Category | Test type (Functional/Integration/etc.) |
| Priority | Test priority |
| Test Suite | Group into suite (optional) |

### 5.2 Write Functional Specification

In the **Specification** field, write plain text describing what to test:

```
Test Sale Order Workflow

PRECONDITIONS:
- User is logged in as Sales Manager
- At least one product exists with price > 0
- At least one customer exists

TEST SCENARIOS:

1. Create New Quotation
   - Navigate to Sales > Orders > Quotations
   - Click Create
   - Select customer "Azure Interior"
   - Add product "Office Chair" quantity 2
   - Verify unit price is populated
   - Verify subtotal = unit price × 2

2. Confirm Quotation
   - Click "Confirm" button
   - Verify state changes to "Sales Order"
   - Verify SO number is generated (starts with "S")

3. Create Invoice
   - Click "Create Invoice"
   - Select "Regular Invoice"
   - Click "Create and View Invoice"
   - Verify invoice is created with correct amount

NEGATIVE TESTS:
- Cannot confirm quotation without order lines
- Cannot set negative quantity
- Cannot select archived customer
```

### 5.3 Analyze Module

Click **Analyze Module** to auto-detect:
- Models and fields
- Views and buttons
- Workflows and states
- Validation rules (from source code)

This information helps AI generate better tests.

---

## 6. Generating Tests

### 6.1 Generate from Specification

On a Test Specification, click **Generate Tests**.

The wizard shows:
- Specification preview
- Module analysis summary
- Generation options

Click **Generate** to start AI processing.

### 6.2 What AI Generates

For each specification, AI creates:

1. **Test Cases** - Individual test scenarios
2. **Test Steps** - Detailed steps with locators
3. **Robot Code** - Executable Robot Framework code

Example generated test:

```robot
*** Test Cases ***
Test Create New Quotation
    [Documentation]    Verify user can create a new quotation
    [Tags]    functional    sales    smoke
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To    Sales    Orders    Quotations
    Click Button    Create
    Select Customer    Azure Interior
    Add Order Line    Office Chair    2
    ${unit_price}=    Get Field Value    price_unit
    ${subtotal}=    Get Field Value    price_subtotal
    Should Be Equal As Numbers    ${subtotal}    ${unit_price} * 2
```

### 6.3 Bulk Generation

From Test Suite view, click **Generate All Tests** to generate for all specifications in the suite.

---

## 7. Running Tests

### 7.1 Run Single Test

On a Test Case, click **Run Test**.

### 7.2 Run Test Suite

On a Test Suite, click **Run Suite**.

Select:
- **Target Server** - Customer's server to test against
- **Environment** - Local/Staging/Production
- **Tags** - Include/exclude specific test tags

### 7.3 Scheduled Runs

Enable scheduled testing:

1. Open Test Suite
2. Click **Enable Schedule**
3. Configure:
   - Interval: Daily/Weekly/Monthly
   - Time: Execution time (24h format)

### 7.4 Jenkins Integration

If Jenkins is configured:
- Tests are submitted to Jenkins
- Results are pulled back automatically
- Build URLs are linked in results

---

## 8. Viewing Results

Navigate to: **QA Testing → Execution → Test Results**

### 8.1 Test Run Summary

Each test run shows:

| Metric | Description |
|--------|-------------|
| Total Tests | Number of tests executed |
| Passed | Tests that passed |
| Failed | Tests that failed |
| Errors | Tests with errors |
| Pass Rate | Percentage passed |
| Duration | Total execution time |

### 8.2 Individual Results

Click on a test result to see:
- Step-by-step execution log
- Screenshots (on failure)
- Error messages
- Execution time per step

### 8.3 Customer Reports

From Customer view, see aggregated metrics:
- Overall pass rate (last 10 runs)
- Last run status
- Trend over time

---

## 9. Best Practices

### 9.1 Writing Good Specifications

✅ **Do:**
- Be specific about expected values
- Include preconditions
- List negative test cases
- Reference actual field names
- Describe validation rules

❌ **Don't:**
- Use vague language ("test the form")
- Skip error scenarios
- Assume context

### 9.2 Organizing Tests

```
Customer: ACME Corp
├── Suite: Smoke Tests
│   ├── Spec: Login/Logout
│   └── Spec: Basic Navigation
├── Suite: Sales Module
│   ├── Spec: Quotation Workflow
│   ├── Spec: Order Confirmation
│   └── Spec: Invoicing
└── Suite: Inventory Module
    ├── Spec: Stock Moves
    └── Spec: Warehouse Transfers
```

### 9.3 Tagging Strategy

| Tag | Purpose |
|-----|---------|
| `smoke` | Quick sanity checks |
| `critical` | Business-critical flows |
| `regression` | Full regression suite |
| `slow` | Long-running tests |
| `manual` | Requires manual intervention |

### 9.4 Environment Strategy

| Environment | Purpose | Frequency |
|-------------|---------|-----------|
| Development | Developer testing | On-demand |
| Staging | QA validation | Daily |
| UAT | User acceptance | Before release |
| Production | Smoke tests only | Post-deploy |

### 9.5 Maintenance

- **Review failed tests** - Fix tests or report bugs
- **Update specs** - When requirements change
- **Regenerate tests** - After major module updates
- **Archive old tests** - Remove obsolete tests

---

## Quick Reference

### Menu Structure

```
QA Testing
├── Customers              → Manage clients
├── Dashboard              → Overview
├── Test Management
│   ├── Test Specifications → Write specs
│   ├── Test Suites        → Group tests
│   └── Test Cases         → View generated tests
├── Execution
│   ├── Test Runs          → Execution history
│   └── Test Results       → Detailed results
└── Configuration
    ├── AI Settings        → API configuration
    ├── Tags               → Test tags
    ├── Module Analysis    → Analyzed modules
    ├── Git Repositories   → Source code repos
    ├── Module Sources     → Module-repo links
    └── All Servers        → All customer servers
```

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Save | `Ctrl+S` |
| New | `Alt+C` |
| Edit | `Alt+A` |
| Discard | `Alt+J` |

### Status Colors

| Color | Meaning |
|-------|---------|
| 🟢 Green | Passed / Success |
| 🔴 Red | Failed / Error |
| 🟡 Yellow | Running / Warning |
| 🔵 Blue | Ready / Info |
| ⚪ Gray | Draft / Pending |

---

## Support

For issues or feature requests, contact your Odoo implementation partner.

**Version:** 18.0.1.0.0
**Last Updated:** January 2026
