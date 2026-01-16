# AI Knowledge Base - User Guide
## Odoo 19 Module

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Module Overview](#module-overview)
4. [Developer Knowledge](#developer-knowledge)
   - Breaking Changes
   - Code Patterns
   - Error Patterns
   - Model Schemas
5. [Consultant Knowledge](#consultant-knowledge)
   - Standard Features
   - Configuration Options
   - Customisation Patterns
   - Limitations
6. [Using the REST API](#using-the-rest-api)
7. [Integration with AI Agents](#integration-with-ai-agents)
8. [Importing Knowledge](#importing-knowledge)
9. [Best Practices](#best-practices)

---

## 1. Introduction

The **AI Knowledge Base** module provides a centralized repository of Odoo knowledge that AI agents can query to:

- **Upgrade code** between Odoo versions with awareness of breaking changes
- **Design solutions** knowing what's standard vs needs customisation
- **Generate tests** with correct locators and patterns
- **Learn from errors** automatically improving over time

### Who Should Use This Module?

| Role | Use Case |
|------|----------|
| **Developers** | Query breaking changes, code patterns, avoid known errors |
| **Consultants** | Quickly assess if requirements need standard/config/custom |
| **AI Agents** | Get context for code generation and solution design |
| **Project Managers** | Estimate effort based on solution approach |

---

## 2. Installation

### Step 1: Download Module

Download `ai_knowledge_base.zip` and extract to your Odoo addons folder:

```bash
cd /path/to/odoo/addons
unzip ai_knowledge_base.zip
mv odoo_knowledge_module ai_knowledge_base
```

### Step 2: Update Apps List

In Odoo:
1. Go to **Apps**
2. Click **Update Apps List**
3. Confirm the update

### Step 3: Install Module

1. Search for "AI Knowledge"
2. Click **Install**

### Step 4: Verify Installation

After installation, you should see **AI Knowledge** in the main menu.

---

## 3. Module Overview

### Menu Structure

```
AI Knowledge
├── Developer
│   ├── Breaking Changes      # API changes between versions
│   ├── Code Patterns         # Reusable code templates
│   ├── Error Patterns        # Auto-learned errors & fixes
│   └── Model Schemas         # Field definitions per version
│
├── Consultant
│   ├── Standard Features     # Out-of-box capabilities
│   ├── Configuration Options # No-code solutions
│   ├── Customisation Patterns# Development patterns
│   └── Limitations           # Known Odoo limitations
│
└── Import Knowledge          # Bulk import wizard
```

### Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Manual Entry  │────▶│                  │────▶│   AI Agents     │
│   Import Files  │     │  Knowledge Base  │     │   REST API      │
│   Auto-Learning │────▶│                  │────▶│   Odoo Shell    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

---

## 4. Developer Knowledge

### 4.1 Breaking Changes

Track API changes between Odoo versions.

**Navigate to:** AI Knowledge → Developer → Breaking Changes

#### Fields

| Field | Description | Example |
|-------|-------------|---------|
| From Version | Source version | 17.0 |
| To Version | Target version | 19.0 |
| Category | Type of change | method_rename |
| Model | Affected model | account.move |
| Field/Method | Specific item | post |
| Description | What changed | post() renamed to action_post() |
| Old Code | Previous syntax | `invoice.post()` |
| New Code | New syntax | `invoice.action_post()` |
| Migration Hint | How to fix | Replace all .post() calls |

#### Categories

- **field_rename** - Field name changed
- **field_remove** - Field removed
- **field_type** - Field type changed
- **method_rename** - Method name changed
- **method_remove** - Method removed
- **method_signature** - Method parameters changed
- **view_change** - View XML structure changed
- **js_change** - JavaScript/OWL changes
- **api_change** - API decorator changes
- **behavior** - Functional behavior changed

#### Example Entry

```
From: 17.0  →  To: 18.0
Category: method_rename
Model: account.move
Method: post
Description: post() method renamed to action_post()
Old Code: invoice.post()
New Code: invoice.action_post()
Migration Hint: Replace all .post() calls with .action_post()
```

---

### 4.2 Code Patterns

Reusable code templates for common development tasks.

**Navigate to:** AI Knowledge → Developer → Code Patterns

#### Fields

| Field | Description |
|-------|-------------|
| Name | Pattern name |
| Category | model, field, method, view, controller, wizard, report, security, js |
| Odoo Version | Specific version or "All" |
| Description | What this pattern does |
| Code Template | The actual code |
| Variables | Placeholders in template |
| Tags | Search keywords |

#### Example: Computed Field Pattern

```python
Name: Computed Field with Store
Category: field
Odoo Version: all

Code Template:
    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
    )
    
    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.line_ids.mapped('amount'))

Variables: field_name, depends_field, line_model
Tags: computed, store, depends, sum
```

---

### 4.3 Error Patterns

Automatically captured errors and their fixes. This is the **learning** component.

**Navigate to:** AI Knowledge → Developer → Error Patterns

#### Fields

| Field | Description |
|-------|-------------|
| Odoo Version | Version where error occurred |
| Task Type | upgrade, enhancement, robot_test, python_test |
| Error Type | Classification of error |
| Error Message | The actual error text |
| Model | Related model |
| Wrong Code | Code that caused error |
| Correct Code | Fixed code |
| Fix Explanation | Why the fix works |
| Occurrences | How many times this error occurred |
| Resolved | Whether fix has been recorded |

#### Error Types

- **field_not_found** - Field doesn't exist
- **method_not_found** - Method/attribute missing
- **import_error** - Import statement failed
- **view_error** - XML view error
- **locator_error** - Robot Framework locator not found
- **other** - Uncategorized

#### How Auto-Learning Works

1. AI agent generates code
2. Code fails with error
3. Error is recorded via API: `POST /api/ai/error`
4. Developer finds correct solution
5. Fix is recorded via API: `POST /api/ai/fix`
6. Next time AI encounters similar error, it knows the fix

---

### 4.4 Model Schemas

Field definitions extracted from Odoo instances.

**Navigate to:** AI Knowledge → Developer → Model Schemas

#### Fields

| Field | Description |
|-------|-------------|
| Model | Model technical name |
| Odoo Version | Version this schema is from |
| Field Count | Number of fields |
| Fields (JSON) | Full field definitions |

#### Extracting Schemas

From Odoo shell:
```python
env['ai.knowledge.service'].extract_schema('sale.order', '19.0')
```

This captures all fields with their types, relations, and attributes.

#### Example Schema JSON

```json
{
  "name": {"type": "char", "string": "Order Reference"},
  "partner_id": {"type": "many2one", "string": "Customer", "relation": "res.partner"},
  "state": {"type": "selection", "string": "Status"},
  "amount_total": {"type": "monetary", "string": "Total"}
}
```

---

## 5. Consultant Knowledge

### 5.1 Standard Features

Document what Odoo does out-of-the-box.

**Navigate to:** AI Knowledge → Consultant → Standard Features

#### Fields

| Field | Description |
|-------|-------------|
| Module | Technical module name (sale, stock, etc.) |
| Category | Functional area |
| Feature Name | Human-readable name |
| Description | What it does |
| Capabilities | What it CAN do (one per line) |
| Limitations | What it CANNOT do (one per line) |
| Edition | community or enterprise |
| Keywords | Search terms |

#### Example: Multi-Warehouse

```
Module: stock
Category: inventory
Feature Name: Multi-Warehouse
Edition: community

Description:
Manage inventory across multiple warehouses with inter-warehouse transfers

Capabilities:
- Multiple warehouse locations
- Inter-warehouse transfers
- Per-warehouse stock levels
- Warehouse-specific routes
- Replenishment rules per warehouse

Limitations:
- No automatic load balancing
- Manual route configuration needed

Keywords: warehouse, multi-warehouse, location, transfer
```

---

### 5.2 Configuration Options

No-code solutions available through settings or Studio.

**Navigate to:** AI Knowledge → Consultant → Configuration Options

#### Fields

| Field | Description |
|-------|-------------|
| Name | Configuration name |
| Module | Related module |
| Config Type | setting, studio, ui, data |
| Description | What it enables |
| Location | Where to find in UI |
| Steps | How to configure |
| Requires Studio | Yes/No |
| Requires Enterprise | Yes/No |
| Complexity | trivial, simple, moderate |
| Estimated Hours | Implementation time |
| Keywords | Search terms |

#### Config Types

| Type | Description | Example |
|------|-------------|---------|
| **setting** | System settings toggle | Enable multi-warehouse |
| **studio** | Odoo Studio customisation | Add approval workflow |
| **ui** | UI configuration | Customize list columns |
| **data** | Data setup | Create price lists |

#### Example: Quotation Approval

```
Name: Quotation Approval Workflow
Module: sale
Config Type: studio
Requires Studio: Yes
Requires Enterprise: Yes
Complexity: simple
Estimated Hours: 2

Description:
Add approval workflow to quotations before sending to customer

Location:
Studio → sale.order → Add Approval

Steps:
1. Open Studio on Sales Order form
2. Click "Add Approval"
3. Configure approval rules
4. Set approvers
5. Save and test

Keywords: approval, quotation approval, sales approval
```

---

### 5.3 Customisation Patterns

When custom development is needed.

**Navigate to:** AI Knowledge → Consultant → Customisation Patterns

#### Fields

| Field | Description |
|-------|-------------|
| Name | Pattern name |
| Pattern Type | field, workflow, report, integration, automation, ui |
| Description | What this pattern achieves |
| When Needed | Situations requiring this |
| Technical Approach | How to implement |
| Code Example | Sample code |
| Complexity | simple, moderate, complex |
| Estimated Days | Development time |
| Risks | Implementation risks |
| Keywords | Search terms |

#### Example: Multi-Level Approval

```
Name: Multi-Level Approval Workflow
Pattern Type: workflow
Complexity: moderate
Estimated Days: 3

Description:
Approval workflow with multiple levels based on amount thresholds

When Needed:
- Different approvers for different amounts
- Sequential approval chain
- Department-based routing

Technical Approach:
1. Add approval state fields
2. Create approval level model
3. Override confirm method
4. Add approval buttons
5. Create notification logic

Code Example:
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    approval_state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ])
    
    def action_request_approval(self):
        level = self._get_approval_level()
        self.write({
            'approval_state': 'pending',
            'current_approver_id': level.approver_id.id,
        })
        self._send_approval_notification()

Risks:
- Complex testing required
- May conflict with other workflows
- Upgrade impact on custom fields

Keywords: approval, multi-level, workflow, threshold
```

---

### 5.4 Limitations

Document what Odoo cannot do well.

**Navigate to:** AI Knowledge → Consultant → Limitations

#### Fields

| Field | Description |
|-------|-------------|
| Area | Functional area |
| Limitation | Short description |
| Description | Detailed explanation |
| Workaround | How to address |
| Workaround Complexity | simple, moderate, complex, not_possible |
| Keywords | Search terms |

#### Example: LIFO Costing

```
Area: inventory
Limitation: No native LIFO costing method

Description:
Odoo supports FIFO, Average Cost (AVCO), and Standard costing 
but does not support Last-In-First-Out (LIFO) inventory valuation.

Workaround:
- Use FIFO with manual journal adjustments
- Custom module to implement LIFO logic
- Third-party LIFO module

Workaround Complexity: complex

Keywords: lifo, costing, inventory valuation, accounting
```

---

## 6. Using the REST API

### Authentication

All API endpoints require authentication. Use session authentication or API keys.

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ai/context/upgrade` | Get upgrade context |
| GET | `/api/ai/context/enhancement` | Get enhancement context |
| GET | `/api/ai/context/test` | Get test generation context |
| GET | `/api/ai/context/consultant` | Get solution design context |
| GET | `/api/ai/check` | Quick solution check |
| POST | `/api/ai/error` | Record an error |
| POST | `/api/ai/fix` | Record a fix |

---

### 6.1 Get Upgrade Context

**Endpoint:** `GET /api/ai/context/upgrade`

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| from_version | Yes | Source version (e.g., 17.0) |
| to_version | Yes | Target version (e.g., 19.0) |
| models | No | Comma-separated model names |

**Example Request:**
```bash
curl -X GET \
  "https://your-odoo.com/api/ai/context/upgrade?from_version=17.0&to_version=19.0&models=sale.order,account.move" \
  -H "Cookie: session_id=YOUR_SESSION"
```

**Example Response:**
```json
{
  "context": "# Upgrade Context: 17.0 → 19.0\n\n## Breaking Changes\n- method_rename: post() renamed to action_post()\n  `invoice.post()` → `invoice.action_post()`\n\n## Model Schemas\n- sale.order: 45 fields\n- account.move: 62 fields\n\n## Known Issues\n- Field not found error... → Use action_post() instead"
}
```

---

### 6.2 Get Enhancement Context

**Endpoint:** `GET /api/ai/context/enhancement`

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| version | No | Odoo version (default: 19.0) |
| models | No | Comma-separated model names |

**Example Request:**
```bash
curl -X GET \
  "https://your-odoo.com/api/ai/context/enhancement?version=19.0&models=sale.order" \
  -H "Cookie: session_id=YOUR_SESSION"
```

---

### 6.3 Get Test Context

**Endpoint:** `GET /api/ai/context/test`

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| version | No | Odoo version (default: 19.0) |
| models | No | Comma-separated model names |
| test_type | No | "robot" or "python" (default: robot) |

**Example Request:**
```bash
curl -X GET \
  "https://your-odoo.com/api/ai/context/test?version=19.0&models=sale.order&test_type=robot" \
  -H "Cookie: session_id=YOUR_SESSION"
```

---

### 6.4 Get Consultant Context

**Endpoint:** `GET /api/ai/context/consultant`

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| requirement | Yes | Business requirement text |
| version | No | Odoo version (default: 19.0) |

**Example Request:**
```bash
curl -X GET \
  "https://your-odoo.com/api/ai/context/consultant?requirement=approval+workflow+for+purchase+orders" \
  -H "Cookie: session_id=YOUR_SESSION"
```

---

### 6.5 Quick Check

**Endpoint:** `GET /api/ai/check`

Returns quick assessment: standard, configuration, or customisation.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| requirement | Yes | Business requirement text |

**Example Request:**
```bash
curl -X GET \
  "https://your-odoo.com/api/ai/check?requirement=track+inventory+multiple+warehouses" \
  -H "Cookie: session_id=YOUR_SESSION"
```

**Example Response:**
```json
{
  "approach": "standard",
  "reason": "Feature: Multi-Warehouse",
  "hours": 1,
  "modules": ["stock"]
}
```

**Possible Approaches:**
| Approach | Meaning |
|----------|---------|
| `standard` | Available out-of-box |
| `configuration` | Needs configuration (no code) |
| `customization` | Requires development |

---

### 6.6 Record Error

**Endpoint:** `POST /api/ai/error`

Record an error for learning.

**Request Body (JSON):**
```json
{
  "version": "19.0",
  "task_type": "upgrade",
  "error_text": "AttributeError: 'account.move' has no attribute 'post'",
  "wrong_code": "invoice.post()",
  "model": "account.move"
}
```

**Response:**
```json
{
  "success": true,
  "error_id": 42
}
```

---

### 6.7 Record Fix

**Endpoint:** `POST /api/ai/fix`

Record a fix for a previously recorded error.

**Request Body (JSON):**
```json
{
  "error_id": 42,
  "correct_code": "invoice.action_post()",
  "explanation": "post() was renamed to action_post() in Odoo 17+"
}
```

**Response:**
```json
{
  "success": true
}
```

---

## 7. Integration with AI Agents

### 7.1 From Odoo Shell

```python
# Get the service
service = env['ai.knowledge.service']

# Get upgrade context
context = service.get_upgrade_context('17.0', '19.0', ['sale.order'])
print(context)

# Get consultant context
context = service.get_consultant_context('approval workflow for POs')
print(context)

# Quick check
result = service.quick_check('multi-warehouse inventory')
print(result)
# {'approach': 'standard', 'reason': 'Feature: Multi-Warehouse', 'hours': 1, 'modules': ['stock']}

# Record error and fix
error = service.record_error('19.0', 'upgrade', 'error msg', 'bad code')
service.record_fix(error.id, 'good code', 'explanation')

# Extract schema from current Odoo
service.extract_schema('sale.order', '19.0')
```

### 7.2 From External Python

Using the standalone `odoo_knowledge_service` package:

```python
from agent_integration import get_agent_kb

# Consultant Agent
kb = get_agent_kb('consultant')
result = kb.quick_check("need approval for orders above $10k")
context = kb.get_context("need approval workflow", version='19.0')

# Upgrade Agent
kb = get_agent_kb('upgrade')
context = kb.get_context(
    from_version='17.0',
    to_version='19.0',
    models=['sale.order'],
    code=old_code
)

# Customisation Agent
kb = get_agent_kb('customisation')
context = kb.get_context(
    version='19.0',
    models=['sale.order'],
    task='Add commission calculation'
)

# QA Agent
kb = get_agent_kb('qa')
context = kb.get_context(
    version='19.0',
    models=['sale.order'],
    test_type='robot'
)
```

### 7.3 Prompt Engineering

Use the context in your AI prompts:

```python
# Get context
context = service.get_upgrade_context('17.0', '19.0', ['sale.order'])

# Build prompt
prompt = f"""
{context}

---

Upgrade the following Odoo 17.0 code to Odoo 19.0:

```python
{old_code}
```

Requirements:
- Fix all deprecated methods and fields
- Maintain the same functionality
- Add comments explaining changes
"""

# Send to AI
response = ai_client.generate(prompt)
```

---

## 8. Importing Knowledge

### 8.1 Using the Import Wizard

**Navigate to:** AI Knowledge → Import Knowledge

1. Click **Import Knowledge**
2. Upload JSON file
3. Click **Import**
4. Review results

### 8.2 JSON File Format

```json
{
  "breaking_changes": [
    {
      "from_version": "17.0",
      "to_version": "19.0",
      "category": "method_rename",
      "model_name": "account.move",
      "method_name": "post",
      "description": "post() renamed to action_post()",
      "old_code": "invoice.post()",
      "new_code": "invoice.action_post()"
    }
  ],
  
  "features": [
    {
      "module": "sale",
      "module_category": "sales",
      "name": "Quotation Management",
      "description": "Create and send quotations",
      "capabilities": "Templates\nEmail PDF\nOnline signature",
      "keywords": "quotation,quote,proposal"
    }
  ],
  
  "configurations": [
    {
      "name": "Enable Variants",
      "module": "product",
      "config_type": "setting",
      "description": "Enable product variants",
      "location": "Settings > Sales > Products",
      "estimated_hours": 1.0,
      "keywords": "variant,attribute,size,color"
    }
  ],
  
  "customisations": [
    {
      "name": "Custom Approval Workflow",
      "pattern_type": "workflow",
      "description": "Multi-level approval based on amount",
      "complexity": "moderate",
      "estimated_days": 3.0,
      "keywords": "approval,workflow"
    }
  ],
  
  "limitations": [
    {
      "area": "inventory",
      "limitation": "No LIFO costing",
      "description": "Odoo does not support LIFO",
      "workaround": "Use FIFO with adjustments",
      "workaround_complexity": "complex",
      "keywords": "lifo,costing"
    }
  ]
}
```

### 8.3 Bulk Import via Shell

```python
import json

# Load file
with open('knowledge.json', 'r') as f:
    data = json.load(f)

# Import breaking changes
for item in data.get('breaking_changes', []):
    env['ai.breaking.change'].create(item)

# Import features
for item in data.get('features', []):
    env['ai.module.feature'].create(item)

# Commit
env.cr.commit()
```

---

## 9. Best Practices

### 9.1 Maintaining Knowledge Quality

1. **Verify entries** - Mark breaking changes as "Verified" after testing
2. **Use keywords** - Add comprehensive keywords for better search
3. **Include examples** - Code patterns should have working examples
4. **Update regularly** - Add new findings after each project

### 9.2 Effective Keywords

Good keywords help AI find relevant knowledge:

```
# Instead of:
keywords: approval

# Use:
keywords: approval, approve, approver, workflow, authorize, sign-off, validate
```

### 9.3 Error Learning Workflow

```
1. AI generates code
2. Code fails → Record error via API
3. Developer debugs → Find correct solution
4. Record fix via API
5. Knowledge improves for next time
```

### 9.4 Consultant Workflow

```
1. Client describes requirement
2. Call quick_check() → Get approach
3. If unclear, call get_consultant_context() → Get full analysis
4. Present options with effort estimates
5. Document decision for future reference
```

### 9.5 Security Considerations

- **Read access**: All users can read knowledge
- **Write access**: Only administrators can modify
- **API access**: Requires authenticated session
- **Sensitive data**: Don't store credentials in code patterns

---

## Appendix A: Model Reference

| Model | Description |
|-------|-------------|
| `ai.breaking.change` | Version breaking changes |
| `ai.code.pattern` | Reusable code templates |
| `ai.error.pattern` | Learned error patterns |
| `ai.model.schema` | Field definitions |
| `ai.module.feature` | Standard features |
| `ai.config.option` | Configuration options |
| `ai.custom.pattern` | Customisation patterns |
| `ai.limitation` | Known limitations |
| `ai.knowledge.service` | Main service (AbstractModel) |
| `ai.import.wizard` | Import wizard (TransientModel) |

---

## Appendix B: Troubleshooting

### API Returns 403 Forbidden

- Ensure user is logged in
- Check session cookie is valid
- Verify user has read access to models

### Import Fails

- Check JSON format is valid
- Ensure required fields are present
- Check for duplicate entries

### Context is Empty

- Verify knowledge has been added
- Check keywords match requirement
- Try broader search terms

### Schema Extraction Fails

- Ensure model exists
- Check user has access to model
- Verify Odoo version selection

---

## Appendix C: Version History

| Version | Changes |
|---------|---------|
| 19.0.1.0.0 | Initial release |

---

**Support:** For issues or feature requests, contact your Odoo administrator.
