{
    'name': 'AI Knowledge Base',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Knowledge base for AI agents',
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
