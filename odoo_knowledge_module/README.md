# AI Knowledge Base - Odoo 19 Module

Knowledge base for AI agents to assist with Odoo development and consulting.

## Features

### Developer Knowledge
- **Breaking Changes**: Track API changes between Odoo versions
- **Code Patterns**: Reusable code templates
- **Error Patterns**: Auto-learned from failures
- **Model Schemas**: Field definitions per version

### Consultant Knowledge
- **Standard Features**: Out-of-box capabilities
- **Configuration Options**: No-code solutions
- **Customisation Patterns**: Development patterns
- **Limitations**: Known Odoo limitations

### Source Code Analyzer (NEW)
- **Auto-parse** Odoo source code from multiple versions
- **Auto-detect** breaking changes (field renames, removals, method changes)
- **Extract schemas** automatically from source
- **Compare versions** and review changes before adding to KB

### OpenUpgrade Importer (NEW)
- **Import from OCA** analysis files directly
- **Thousands of changes** documented by the community
- **Preview and select** which changes to import
- **Bulk import** from a local OpenUpgrade clone

## OpenUpgrade Importer - Usage

The fastest way to populate your KB with breaking changes!

### Option 1: Upload Analysis File

1. Go to **AI Knowledge Base > Source Analyzer > OpenUpgrade Importer**
2. Select "Upload File" 
3. Download an analysis file from [OCA/OpenUpgrade](https://github.com/OCA/OpenUpgrade)
   - Path: `openupgrade_scripts/scripts/{module}/{version}/openupgrade_analysis.txt`
4. Upload and click "Parse & Preview"
5. Review changes and click "Import Selected"

### Option 2: Clone and Bulk Import

```bash
# Clone the OpenUpgrade repository
git clone https://github.com/OCA/OpenUpgrade /opt/OpenUpgrade
cd /opt/OpenUpgrade
git checkout 18.0  # or 17.0, 19.0, etc.
```

Then in Odoo:
1. Go to **AI Knowledge Base > Source Analyzer > OpenUpgrade Importer**
2. Select "GitHub (Manual Clone)"
3. Enter path: `/opt/OpenUpgrade`
4. Select target version (e.g., 18.0)
5. Click "Import from Clone"

This imports **ALL** analysis files from all modules!

## Source Code Analyzer - Usage

### Step 1: Add Odoo Source Versions

Go to **AI Knowledge Base > Source Analyzer > Odoo Sources**

Create records pointing to your Odoo source directories:

| Version | Path |
|---------|------|
| 17.0 | `/opt/odoo17/odoo/addons` |
| 18.0 | `/opt/odoo18/odoo/addons` |
| 19.0 | `/opt/odoo19/odoo/addons` |

You can also include enterprise addons:
| Version | Path |
|---------|------|
| 19.0 EE | `/opt/odoo19/enterprise` |

### Step 2: Analyze Each Version

Click **"Analyze Source"** on each version. The analyzer will:

1. Find all modules (look for `__manifest__.py`)
2. Parse Python files using AST
3. Extract: models, fields, methods, decorators
4. Store results in JSON format

### Step 3: Compare Versions

Go to **AI Knowledge Base > Source Analyzer > Version Comparisons**

1. Create new comparison (e.g., 17.0 → 18.0)
2. Click **"Compare Versions"**
3. Review detected changes:
   - Field renamed
   - Field removed
   - Field type changed
   - Method renamed
   - Method removed
   - Method signature changed

### Step 4: Approve and Create KB Entries

1. Review each change (high confidence = usually correct)
2. Click **"Approve High Confidence"** or approve individually
3. Click **"Create KB Entries"** to add to Knowledge Base

## REST API

```bash
# Get upgrade context
GET /api/ai/context/upgrade?from_version=17.0&to_version=19.0&models=sale.order

# Get enhancement context
GET /api/ai/context/enhancement?version=19.0&models=sale.order

# Get test context
GET /api/ai/context/test?version=19.0&test_type=robot

# Get consultant context
GET /api/ai/context/consultant?requirement=approval+workflow

# Quick check
GET /api/ai/check?requirement=quotation+approval

# Record error (POST JSON)
POST /api/ai/error
{"version": "19.0", "task_type": "upgrade", "error_text": "...", "wrong_code": "..."}

# Record fix (POST JSON)
POST /api/ai/fix
{"error_id": 1, "correct_code": "...", "explanation": "..."}
```

## Installation

1. Copy module to addons folder
2. Update app list
3. Install "AI Knowledge Base"

## Usage from Python

```python
# In Odoo shell or custom module
service = env['ai.knowledge.service']

# Get context for AI prompt
context = service.get_upgrade_context('17.0', '19.0', ['sale.order'])

# Quick check
result = service.quick_check('need approval workflow')
# {'approach': 'configuration', 'reason': '...', 'hours': 2}

# Record errors for learning
error = service.record_error('19.0', 'upgrade', 'error msg', 'bad code')
service.record_fix(error.id, 'good code', 'explanation')
```

## Using the Mixin in Your Agent

```python
class MyAgent(models.Model):
    _name = 'my.agent'
    _inherit = ['mail.thread', 'ai.kb.mixin']  # Add mixin
    
    def do_something(self):
        # Get context for AI prompts
        context = self.kb_get_upgrade_context('17.0', '19.0', ['sale.order'])
        
        # Find known fixes for an error
        fixes = self.kb_get_error_patterns(error_message, 'upgrade')
        
        # Record a new error
        error_id = self.kb_record_error('19.0', 'upgrade', error_msg, wrong_code)
        
        # After verifying fix works, save it
        self.kb_record_fix(error_id, correct_code, 'Explanation')
```
