{
    'name': 'AI Data Migration Toolkit',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'AI-powered data migration with intelligent field mapping and validation',
    'description': """
AI Data Migration Toolkit
=========================

A comprehensive data migration solution featuring:

* **AI-Powered Field Mapping**: Automatically suggests mappings between source columns and Odoo fields
* **Data Validation**: Pre-import validation with detailed error reporting
* **Transformation Rules**: Built-in and custom data transformations
* **Multi-Model Support**: Migrate to any Odoo model
* **Batch Processing**: Handle large datasets with chunked imports
* **Audit Trail**: Complete logging of all migration activities
* **Rollback Support**: Undo migrations if issues are discovered
* **Template Library**: Save and reuse migration configurations

Supported Source Formats:
* CSV files
* Excel files (XLSX, XLS)
* JSON files

Typical Use Cases:
* Initial ERP implementation data loads
* System migrations from legacy software
* Periodic bulk data updates
* Multi-system data consolidation
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'base_import',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/transformation_rules.xml',
        'data/cron_jobs.xml',
        'views/migration_mapping_views.xml',
        'views/migration_template_views.xml',
        'views/migration_log_views.xml',
        'views/migration_project_views.xml',
        'views/migration_agent_views.xml',
        'wizards/import_wizard_views.xml',
        'wizards/ai_mapping_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_data_migration/static/src/css/migration.css',
            'ai_data_migration/static/src/js/migration_widget.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
