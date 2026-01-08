# QA Test Generator

AI-Powered Test Automation for Odoo using Robot Framework

## Overview

QA Test Generator is a comprehensive Odoo module that enables QA teams to generate, manage, and execute automated tests using AI (Claude) and Robot Framework.

## Features

- **AI-Powered Test Generation**: Write functional specifications in plain text, and AI generates Robot Framework tests
- **Module Analysis**: Automatically detects models, views, fields, and buttons from Odoo modules
- **Test Management**: Organize tests into suites, tag them, and track results
- **Jenkins Integration**: Execute tests via Jenkins CI/CD pipeline
- **Dashboard**: Visual overview of test status, pass rates, and recent runs
- **Email Notifications**: Get notified when test runs complete

## Installation

1. Copy the `qa_test_generator` folder to your Odoo addons directory
2. Update the apps list in Odoo
3. Install the module from Apps menu

## Configuration

1. Go to **QA Testing > Configuration > AI Settings**
2. Enter your Anthropic API key
3. Configure test environment settings (URL, credentials)
4. Optionally configure Jenkins integration

## Quick Start

### 1. Create a Test Specification

```
QA Testing > Test Management > Test Specifications > Create

Name: Invoice Creation Flow
Module: account (Invoicing)
Specification:
1. User navigates to Invoicing > Customers > Invoices
2. User clicks 'New' to create a new invoice
3. User selects customer 'Test Company'
4. User adds a product line with Product: 'Service', Quantity: 2, Price: 500
5. User clicks 'Confirm' to validate the invoice
6. Verify the invoice status changes to 'Posted'
7. Verify the total amount is 1000
```

### 2. Analyze Module (Optional)

Click **Analyze Module** to extract models, views, and fields for better test generation.

### 3. Generate Tests

Click **Generate Tests** - AI will create Robot Framework test cases.

### 4. Run Tests

- Click **Run Tests** on individual test cases, or
- Create a Test Suite and run all tests together

### 5. View Results

Check the Dashboard or go to **Execution > Test Results** to see outcomes.

## API Endpoints

### Create Test Run
```bash
POST /qa_test/api/run
{
    "suite_id": 1,
    "environment": "staging",
    "auto_execute": true
}
```

### Get Run Status
```bash
GET /qa_test/api/run/<run_id>/status
```

### Generate Tests
```bash
POST /qa_test/api/generate
{
    "spec_id": 1,
    "analyze_first": true
}
```

## Requirements

- Odoo 16.0 / 17.0 / 18.0
- Robot Framework (`pip install robotframework`)
- SeleniumLibrary (`pip install robotframework-seleniumlibrary`)
- Chrome/Firefox browser driver
- Anthropic API key (for AI generation)

## Support

For issues or questions, contact your QA team lead.

## License
LGPL-3
