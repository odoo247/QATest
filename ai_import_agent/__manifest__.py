# -*- coding: utf-8 -*-
{
    'name': 'AI Import Agent',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Intelligent data import with AI-powered mapping and error handling',
    'description': '''
AI Import Agent
===============

Intelligent data import agent that uses the AI Knowledge Base to:

Features:
---------
* Import from CSV, Excel, JSON files
* Auto-detect and suggest field mappings
* Validate data before import
* Smart error handling with KB lookup
* Learn from import errors
* Batch processing with progress tracking

Usage:
------
1. Create new Import Job
2. Upload your data file
3. Select target Odoo model
4. Review/adjust field mappings
5. Validate data
6. Execute import

The agent will:
- Use KB to understand field types and constraints
- Look up known error patterns when issues occur
- Record new errors for future learning
    ''',
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'odoo_knowledge_module',  # AI Knowledge Base
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/import_job_views.xml',
        'views/menu_views.xml',
        'data/error_patterns.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
