# AI Data Migration Toolkit for Odoo

A comprehensive, AI-powered data migration module for Odoo 17+ that streamlines the process of importing data from external sources (CSV, Excel, JSON) into any Odoo model.

## Features

### 🤖 AI-Powered Field Mapping
- **Intelligent Column Matching**: Uses Claude or GPT to analyze source columns and suggest appropriate Odoo field mappings
- **Confidence Scoring**: Each suggestion includes a confidence score to help you prioritize review
- **Reasoning Explanations**: AI provides explanations for its mapping decisions

### 📊 Data Quality Analysis
- **Pre-Import Validation**: Identifies data quality issues before import
- **Format Detection**: Automatically detects date formats, numeric patterns, etc.
- **Duplicate Detection**: Warns about potential duplicate records
- **Issue Recommendations**: AI suggests fixes for common data problems

### 🔄 Flexible Data Transformation
- **Built-in Transformations**: 20+ pre-configured transformation rules
- **Custom Rules**: Create your own transformation logic
- **Chained Transformations**: Apply multiple transformations in sequence
- **Preview**: Test transformations before running the full import

### 📁 Multi-Format Support
- CSV files (with configurable delimiter and encoding)
- Excel files (XLSX, XLS)
- JSON files (arrays or nested structures)

### 🎯 Import Management
- **Batch Processing**: Handle large datasets with configurable batch sizes
- **Error Handling**: Choose to stop, skip, or log errors
- **Progress Tracking**: Real-time progress monitoring
- **Rollback Support**: Undo imports if issues are discovered

### 📋 Templates & Reusability
- **Save Configurations**: Save successful mappings as templates
- **Share Templates**: Make templates available to team members
- **Template Tags**: Organize templates by category

## Installation

1. Copy the `ai_data_migration` folder to your Odoo addons directory
2. Update the addons list: `Settings > Apps > Update Apps List`
3. Install the module: Search for "AI Data Migration" and click Install

### Dependencies

```bash
# Required Python packages
pip install openpyxl  # For Excel file support
pip install requests  # For AI API calls
```

### AI Service Configuration

Configure your AI provider API key in System Parameters:

```
Settings > Technical > System Parameters
```

Add one of:
- `migration.ai.anthropic_api_key` - For Claude
- `migration.ai.openai_api_key` - For GPT

Or configure per-project in the project settings.

## Quick Start

### 1. Quick Import Wizard

The fastest way to start:

1. Go to **Data Migration > Quick Import**
2. Upload your file
3. Select the target model
4. Click **Create Project**
5. Use AI to auto-map fields

### 2. Create a Migration Project

For more control:

1. Go to **Data Migration > Migration Projects**
2. Click **Create**
3. Configure:
   - **Source File**: Upload CSV, Excel, or JSON
   - **Target Model**: Select destination (e.g., `res.partner`)
   - **Import Settings**: Batch size, error handling, etc.

### 3. AI Field Mapping

1. After uploading your file, click **AI Mapping**
2. Configure AI options:
   - Provider (Claude or GPT)
   - Include data quality analysis
   - Auto-accept high-confidence mappings
3. Click **Analyze with AI**
4. Review suggestions and adjust as needed
5. Click **Apply Selected Mappings**

### 4. Validate & Import

1. Click **Validate** to check your configuration
2. Review any warnings or errors
3. Click **Start Import**
4. Monitor progress in real-time

## Field Mapping Guide

### Mapping Types

| Type | Description |
|------|-------------|
| Direct | Map source column directly to target field |
| Transform | Apply transformations before mapping |
| Default | Use a default value when source is empty |
| Skip | Ignore this source column |

### Relational Fields

For `many2one` and `many2many` fields:

1. **Search Field**: Specify which field to search (default: `name`)
2. **Create if Missing**: Optionally create related records
3. **Multi-value Delimiter**: For many2many, specify how values are separated

Example: Mapping a "Category" column to `product.category`:
- Set Search Field to `name`
- Enable "Create if Missing" to auto-create new categories

### Selection Fields

Use **Value Mapping** to translate source values:

```json
{
    "Active": "active",
    "Inactive": "inactive",
    "Pending": "draft"
}
```

## Transformation Rules

### Built-in Transformations

#### String Transformations
- `uppercase` - Convert to UPPERCASE
- `lowercase` - Convert to lowercase
- `titlecase` - Convert To Title Case
- `trim` - Remove whitespace
- `replace` - Find and replace text
- `regex_replace` - Regex-based replacement

#### Numeric Transformations
- `clean_numeric` - Remove currency symbols
- `round` - Round to decimal places
- `multiply`, `divide`, `add`, `subtract`
- `abs` - Absolute value

#### Date Transformations
- `date_format` - Convert between date formats
- `date_add_days` - Add/subtract days
- `date_to_year` - Extract year
- `date_to_month` - Extract month

#### Special Transformations
- `value_map` - Map values using lookup table
- `conditional` - If/then/else logic
- `coalesce` - Use first non-empty value
- `python` - Custom Python expression (admin only)

### Creating Custom Rules

1. Go to **Data Migration > Configuration > Transformation Rules**
2. Click **Create**
3. Configure:
   - Name and description
   - Transformation type
   - Parameters (JSON format)

Example - Currency conversion:
```json
{
    "name": "AUD to USD",
    "transformation_type": "multiply",
    "transformation_params": "{\"factor\": 0.65}"
}
```

## Templates

### Saving a Template

After a successful migration:

1. Click **Save as Template**
2. Enter a name and description
3. Optionally share with team
4. Add tags for organization

### Using a Template

1. Create a new project
2. Select the template from dropdown
3. Click **Apply Template**
4. Upload your file (columns should match)

## API Integration

### Using with External Systems

The module exposes methods for programmatic use:

```python
# Create a migration project programmatically
project = env['migration.project'].create({
    'name': 'API Import',
    'source_type': 'csv',
    'target_model_id': env.ref('base.model_res_partner').id,
})

# Attach file
project.write({
    'source_file': base64.b64encode(csv_content),
    'source_filename': 'partners.csv',
})

# Parse and get AI suggestions
project._parse_source_file()
suggestions = env['migration.ai.service'].suggest_mappings(project)

# Run import
project.action_validate()
project.action_start_import()
```

## Security

### User Groups

| Group | Permissions |
|-------|-------------|
| Migration User | Create/run own projects, view templates |
| Migration Manager | Manage all projects, templates, and settings |

### Best Practices

1. **Test First**: Always run a test import with a small dataset
2. **Backup**: Ensure database backups before large imports
3. **Review AI Suggestions**: Don't blindly accept all AI mappings
4. **Use Templates**: Save working configurations for reuse

## Troubleshooting

### Common Issues

**"AI API key not configured"**
- Set the API key in System Parameters or in the project settings

**"Cannot parse file"**
- Check file encoding (try UTF-8 or Latin-1)
- Verify delimiter for CSV files
- Ensure Excel file is not password-protected

**"Required field not mapped"**
- Map all required fields (marked in red)
- Or set a default value for the mapping

**Import errors**
- Check the Migration Logs for details
- Review the row data for problematic records
- Adjust error handling (skip vs. stop)

### Performance Tips

1. **Batch Size**: Use 100-500 for optimal performance
2. **Large Files**: For 10k+ records, consider splitting the file
3. **Indexes**: Ensure target model fields have indexes
4. **Cron**: For very large imports, use the background cron job

## Changelog

### Version 17.0.1.0.0
- Initial release
- AI-powered field mapping (Claude & GPT)
- Data quality analysis
- 20+ built-in transformations
- Template system
- Multi-format support (CSV, Excel, JSON)

## Support

For issues, questions, or feature requests:
- Create an issue in the repository
- Contact: support@yourcompany.com

## License

LGPL-3.0

---

Built with ❤️ for the Odoo community
