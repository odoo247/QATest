# -*- coding: utf-8 -*-
{
    'name': 'QA Test Generator',
    'version': '18.0.2.1.0',
    'category': 'Productivity/Testing',
    'summary': 'AI-Powered QA Testing for Odoo ERP Implementations',
    'description': """
QA Test Generator - Complete ERP Implementation Testing Platform
================================================================

This module provides a comprehensive solution for QA testing across
multiple customer implementations, with AI-powered test generation,
health monitoring, and regression testing.

Key Features
------------
* **Code-First Testing**: Scan Git repos, auto-generate tests from source code
* **Requirement-Driven Testing**: Link tests to customer requirements
* **AI Test Generation**: Claude AI generates Robot Framework tests
* **Multi-Customer Support**: Manage QA for unlimited customers
* **Health Monitoring**: Track integrations, data integrity, Studio changes
* **Regression Testing**: Pre-built templates for standard Odoo modules
* **Jenkins Integration**: CI/CD pipeline support

What Can Break?
---------------
1. YOUR CHANGES - Custom modules, bug fixes, upgrades
2. CUSTOMER CHANGES - Odoo Studio, settings, access rights
3. INTEGRATIONS - APIs, EDI, payment gateways, shipping
4. DATA INTEGRITY - Orphaned records, broken links, imbalances
5. INFRASTRUCTURE - Server resources, database, backups
6. SCHEDULED JOBS - Cron failures, email queues

This module helps you catch ALL of these issues before they impact customers.

Configuration
-------------
1. Install the module
2. Go to QA Testing > Configuration > AI Settings
3. Enter your Anthropic API key
4. Add customers and their Git repositories
5. Use Code Scanning to generate tests from source code
6. Or create requirements and generate acceptance tests
7. Set up health checks for integrations
8. Generate regression test suites

Technical Requirements
----------------------
* Robot Framework
* Selenium or Playwright
* Anthropic API key (Claude)
* Jenkins (optional, for CI/CD)
* Git (for code scanning)
    """,
    'author': 'QA Automation Team',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/config_data.xml',
        'data/cron_data.xml',
        'data/mail_template_data.xml',
        # Views - ORDER MATTERS! Actions must exist before being referenced
        'views/customer_views.xml',
        'views/ai_config_views.xml',
        'views/git_repository_views.xml',
        'views/code_scan_views.xml',
        'views/test_spec_views.xml',
        'views/test_case_views.xml',
        'views/test_suite_views.xml',
        'views/test_result_views.xml',
        # These reference test_case action, must come AFTER
        'views/requirement_views.xml',
        'views/health_check_views.xml',
        'views/regression_views.xml',
        'views/dashboard_views.xml',
        # Menus (loaded AFTER actions)
        'views/menu_views.xml',
        # Wizards
        'wizards/views/generate_tests_wizard_views.xml',
        'wizards/views/run_tests_wizard_views.xml',
    ],
    # Dashboard assets commented out - can be added once core is working
    # 'assets': {
    #     'web.assets_backend': [
    #         'qa_test_generator/static/src/css/dashboard.css',
    #         'qa_test_generator/static/src/js/dashboard.js',
    #         'qa_test_generator/static/src/xml/dashboard.xml',
    #     ],
    # },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
