{
    'name': 'AI Knowledge Base',
    'version': '18.0.2.0.0',
    'category': 'Technical',
    'summary': 'Knowledge base for AI agents with source code analysis',
    'description': '''
AI Knowledge Base for Odoo
==========================

Central knowledge repository for AI agents (QA, Upgrade, Consultant, etc.)

Features:
---------
* Breaking changes between Odoo versions
* Code patterns and templates
* Error patterns with verified fixes
* Model schemas per version
* Module features and capabilities
* Configuration options
* Known limitations

Source Code Analyzer (NEW):
---------------------------
* Parse Odoo source code from multiple versions
* Auto-detect breaking changes between versions
* Extract model schemas automatically
* Compare fields, methods, decorators

Usage:
------
1. Add Odoo source paths for each version
2. Run "Analyze Source" on each version
3. Create a Version Comparison
4. Review and approve detected changes
5. Create KB entries from approved changes
    ''',
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        # 1. Security first
        'security/ir.model.access.csv',
        # 2. Root menus (no action dependencies)
        'views/menu_root.xml',
        # 3. Views with actions
        'views/breaking_change_views.xml',
        'views/code_pattern_views.xml',
        'views/error_pattern_views.xml',
        'views/model_schema_views.xml',
        'views/module_feature_views.xml',
        'views/config_option_views.xml',
        'views/custom_pattern_views.xml',
        'views/limitation_views.xml',
        'views/source_analyzer_views.xml',
        # 4. Wizard with action
        'wizards/import_wizard_views.xml',
        # 5. Menus that reference actions (LAST)
        'views/menu_views.xml',
        # 6. Seed data
        'data/seed_data.xml',
    ],
    'installable': True,
    'application': True,
}
