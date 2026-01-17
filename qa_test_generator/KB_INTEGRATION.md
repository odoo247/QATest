# Knowledge Base Integration

## Overview

The QA Test Generator integrates with the **AI Knowledge Base** via a mixin class.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│            SAME ODOO INSTANCE / DATABASE            │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ QA Test      │  │ Other Agent  │                 │
│  │ Generator    │  │ Modules      │                 │
│  │              │  │              │                 │
│  │ inherits     │  │ inherits     │                 │
│  │ ai.kb.mixin  │  │ ai.kb.mixin  │                 │
│  └──────┬───────┘  └──────┬───────┘                 │
│         │                 │                         │
│         └────────┬────────┘                         │
│                  │                                  │
│           ┌──────▼──────┐                           │
│           │ ai.kb.mixin │  (AbstractModel)          │
│           └──────┬──────┘                           │
│                  │                                  │
│           ┌──────▼──────┐                           │
│           │    KB       │                           │
│           │   Module    │                           │
│           │ (odoo_      │                           │
│           │ knowledge_  │                           │
│           │ module)     │                           │
│           └─────────────┘                           │
└─────────────────────────────────────────────────────┘
```

## How to Use in Any Agent

### 1. Add Dependency

```python
# __manifest__.py
{
    'depends': ['base', 'mail', 'odoo_knowledge_module'],
}
```

### 2. Inherit Mixin

```python
# models/my_model.py
class MyAgentModel(models.Model):
    _name = 'my.agent.model'
    _inherit = ['mail.thread', 'ai.kb.mixin']  # Add mixin
```

### 3. Use KB Methods

```python
def generate_something(self):
    # Get context for AI prompts
    context = self.kb_get_test_context('19.0', ['sale.order'], 'robot')
    
    # Get error patterns
    patterns = self.kb_get_error_patterns(error_msg, 'robot_test')
    
    # Record an error
    error_id = self.kb_record_error('19.0', 'robot_test', error_msg, wrong_code)
    
    # Record a verified fix
    self.kb_record_fix(error_id, correct_code, 'Explanation')
```

## Available Mixin Methods

| Method | Purpose |
|--------|---------|
| `kb_get_context(version, task_type, models)` | General context |
| `kb_get_test_context(version, models, test_type)` | Test generation context |
| `kb_get_upgrade_context(from_ver, to_ver, models)` | Upgrade/migration context |
| `kb_get_error_patterns(error, task_type, model)` | Find matching errors |
| `kb_record_error(version, task, error, code)` | Record new error |
| `kb_record_fix(error_id, code, explanation)` | Record verified fix |
| `kb_get_code_patterns(category, version)` | Get code templates |
| `kb_get_breaking_changes(from_ver, to_ver)` | Get breaking changes |
| `kb_is_available()` | Check if KB is accessible |

## Benefits

- **No code duplication** - Mixin defined once in KB module
- **Direct ORM access** - Fast, same database
- **Auto-updates** - Update KB module, all agents benefit
- **Shared learning** - Fixes from any agent help all agents

