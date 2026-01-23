# AI Import Agent

Intelligent data import agent for Odoo that uses the AI Knowledge Base for smart field mapping and error handling.

## Features

- **Multi-format Support**: Import from CSV, Excel (xlsx), and JSON files
- **Auto Field Mapping**: Automatically maps source columns to Odoo fields
- **Data Validation**: Validates data before import
- **Smart Error Handling**: Looks up errors in KB for known fixes
- **Learning**: Records new error patterns to KB for future imports
- **Batch Processing**: Handles large files with progress tracking
- **Update Mode**: Can update existing records instead of creating duplicates

## Installation

1. Install the AI Knowledge Base module first (`odoo_knowledge_module`)
2. Install this module (`ai_import_agent`)
3. Install `openpyxl` for Excel support: `pip install openpyxl`

## Usage

### 1. Create Import Job

Go to **AI Knowledge > Import Agent > New Import**

### 2. Upload File

- Upload your CSV, Excel, or JSON file
- Click **Parse File** to analyze the structure

### 3. Select Target Model

Choose the Odoo model you want to import into (e.g., `res.partner`, `product.product`)

### 4. Map Fields

- Click **Auto-Map Fields** for automatic mapping
- Review and adjust mappings manually if needed
- Set transforms (uppercase, lowercase, etc.)
- Set default values for empty fields

### 5. Validate

Click **Validate** to check data before import:
- Required fields check
- Data type validation
- Format verification

### 6. Import

Click **Import** to start:
- Progress tracking
- Error handling with KB lookup
- Batch commits for large files

### 7. Learn from Errors

If errors occur:
- Click on errors to see details
- **Lookup in KB** for known fixes
- **Record to KB** to save new error patterns
- **Record Fix** after resolving to help future imports

## Import Options

| Option | Description |
|--------|-------------|
| **Update Existing** | Update records if they exist (matched by key field) |
| **Key Field** | Field used to identify existing records |
| **Skip Errors** | Continue importing even if some rows fail |
| **Batch Size** | Records per batch (default: 100) |

## Field Mapping

| Column | Description |
|--------|-------------|
| **Source Column** | Column name from your file |
| **Sample Values** | First few values (for reference) |
| **Target Field** | Odoo field to map to |
| **Transform** | Optional: UPPERCASE, lowercase, Title Case, Strip |
| **Default Value** | Value to use if source is empty |
| **Confidence** | Auto-map confidence (High/Medium/Low/Manual) |
| **Skip** | Don't import this column |

## Supported Field Types

| Type | Handling |
|------|----------|
| **Char/Text** | Direct mapping |
| **Integer** | Parsed, removes commas |
| **Float/Monetary** | Parsed, removes currency symbols |
| **Boolean** | Accepts: true, 1, yes, y, x |
| **Date** | Multiple formats: YYYY-MM-DD, DD/MM/YYYY, etc. |
| **Datetime** | Multiple formats with time |
| **Many2one** | Searches by name or ID |
| **Selection** | Direct value mapping |

## KB Integration

The Import Agent uses the AI Knowledge Base for:

1. **Schema Information**: Knows field types, required fields
2. **Error Patterns**: Looks up known fixes for import errors
3. **Learning**: Records new error patterns for future reference

## Sample Files

### CSV Format
```csv
name,email,phone,company_name
John Doe,john@example.com,+1234567890,ACME Corp
Jane Smith,jane@example.com,+0987654321,Tech Inc
```

### JSON Format
```json
[
  {"name": "John Doe", "email": "john@example.com"},
  {"name": "Jane Smith", "email": "jane@example.com"}
]
```

## Common Issues & Fixes

| Error | Fix |
|-------|-----|
| Required field empty | Add default value or fix source data |
| Duplicate key | Enable "Update Existing" or remove duplicates |
| Related record not found | Import parent records first |
| Invalid date format | Use YYYY-MM-DD format |
| Encoding error | Save file as UTF-8 |

## API / Programmatic Use

```python
# Create import job
job = env['ai.import.job'].create({
    'name': 'Partner Import',
    'target_model_id': env.ref('base.model_res_partner').id,
})

# Upload file
job.write({
    'file_data': base64.b64encode(file_content),
    'file_name': 'partners.csv',
})

# Parse and auto-map
job.action_parse_file()
job.action_auto_map()

# Validate and import
job.action_validate()
job.action_import()

# Check results
print(f"Success: {job.success_count}, Errors: {job.error_count}")
```
