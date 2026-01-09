# -*- coding: utf-8 -*-
{
    'name': 'QA Test Generator',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Testing',
    'summary': 'AI-Powered Test Generation for Odoo',
    'description': """
QA Test Generator - AI-Powered Automated Testing
=================================================

This module provides a complete solution for automated test generation
and execution using AI (Claude) and Robot Framework.

Features
--------
* Write functional specifications in plain text
* AI automatically analyzes Odoo modules (models, views, fields)
* Fetches source code from GitHub/GitLab/Bitbucket for deep analysis
* Generates Robot Framework test cases with negative scenarios
* Integrates with Jenkins for CI/CD
* Dashboard for test results and analytics
* Screenshot capture on failures
* Email notifications

Configuration
-------------
1. Install the module
2. Go to QA Testing > Configuration > AI Settings
3. Enter your Anthropic API key
4. Configure Git repository for source code access
5. Configure Jenkins connection (optional)
6. Start creating test specifications!

Technical Requirements
----------------------
* Robot Framework
* Selenium or Playwright
* Anthropic API key (Claude)
* Jenkins (optional, for CI/CD)
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
        # Views
        'views/menu_views.xml',
        'views/ai_config_views.xml',
        'views/git_repository_views.xml',
        'views/test_spec_views.xml',
        'views/test_case_views.xml',
        'views/test_suite_views.xml',
        'views/test_result_views.xml',
        'views/dashboard_views.xml',
        # Wizards
        'wizards/views/generate_tests_wizard_views.xml',
        'wizards/views/run_tests_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'qa_test_generator/static/src/css/dashboard.css',
            'qa_test_generator/static/src/js/dashboard.js',
            'qa_test_generator/static/src/xml/dashboard.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
