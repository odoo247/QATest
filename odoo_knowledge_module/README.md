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
