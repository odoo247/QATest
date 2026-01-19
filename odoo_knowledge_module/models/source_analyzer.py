# -*- coding: utf-8 -*-
"""
Odoo Source Code Analyzer

Parses Odoo source code across multiple versions to automatically
generate Knowledge Base entries (breaking changes, schemas, patterns).

Usage:
    1. Create ai.odoo.source records pointing to each version's source
    2. Run "Analyze All" to parse and extract metadata
    3. Run "Compare Versions" to detect breaking changes
    4. Review and approve generated KB entries
"""

import os
import ast
import json
import logging
import hashlib
from pathlib import Path
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AiOdooSource(models.Model):
    """Odoo source code location for a specific version."""
    _name = 'ai.odoo.source'
    _description = 'Odoo Source Version'
    _order = 'version desc'

    name = fields.Char('Name', compute='_compute_name', store=True)
    version = fields.Selection([
        ('13.0', '13.0'), ('14.0', '14.0'), ('15.0', '15.0'),
        ('16.0', '16.0'), ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], string='Odoo Version', required=True, index=True)
    
    source_type = fields.Selection([
        ('local', 'Local Path'),
        ('git', 'Git Repository'),
    ], string='Source Type', default='local', required=True)
    
    # Local path
    source_path = fields.Char('Source Path', 
        help='Local path to Odoo source, e.g., /opt/odoo17/odoo/addons')
    
    # Git (future)
    git_url = fields.Char('Git URL',
        help='e.g., https://github.com/odoo/odoo.git')
    git_branch = fields.Char('Branch', default='17.0')
    
    # Analysis state
    state = fields.Selection([
        ('draft', 'Not Analyzed'),
        ('analyzing', 'Analyzing...'),
        ('done', 'Analyzed'),
        ('error', 'Error'),
    ], default='draft')
    
    last_analyzed = fields.Datetime('Last Analyzed')
    error_message = fields.Text('Error')
    
    # Statistics
    module_count = fields.Integer('Modules', readonly=True)
    model_count = fields.Integer('Models', readonly=True)
    field_count = fields.Integer('Fields', readonly=True)
    method_count = fields.Integer('Methods', readonly=True)
    
    # Parsed data (JSON storage)
    parsed_data = fields.Text('Parsed Data (JSON)', 
        help='Full parsed metadata in JSON format')
    
    active = fields.Boolean(default=True)

    @api.depends('version', 'source_type')
    def _compute_name(self):
        for rec in self:
            rec.name = f"Odoo {rec.version} ({rec.source_type})"

    def action_analyze(self):
        """Parse the Odoo source and extract metadata."""
        self.ensure_one()
        
        if self.source_type == 'local':
            if not self.source_path:
                raise UserError('Please set the source path.')
            if not os.path.isdir(self.source_path):
                raise UserError(f'Path not found: {self.source_path}')
        else:
            raise UserError('Git source not yet implemented. Use local path.')
        
        self.state = 'analyzing'
        self.error_message = False
        
        try:
            parser = OdooSourceParser(self.source_path, self.version)
            result = parser.parse_all()
            
            self.write({
                'state': 'done',
                'last_analyzed': fields.Datetime.now(),
                'module_count': result['stats']['modules'],
                'model_count': result['stats']['models'],
                'field_count': result['stats']['fields'],
                'method_count': result['stats']['methods'],
                'parsed_data': json.dumps(result, indent=2, default=str),
            })
            
            # Auto-generate model schemas
            self._generate_schemas(result)
            
            _logger.info(f"Analyzed Odoo {self.version}: {result['stats']}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Analysis Complete',
                    'message': f"Parsed {result['stats']['models']} models, {result['stats']['fields']} fields",
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.exception(f"Analysis failed for {self.version}")
            self.write({
                'state': 'error',
                'error_message': str(e),
            })
            raise UserError(f'Analysis failed: {e}')

    def _generate_schemas(self, result):
        """Generate ai.model.schema records from parsed data."""
        Schema = self.env['ai.model.schema']
        
        for model_name, model_data in result.get('models', {}).items():
            fields_info = {}
            for field_name, field_data in model_data.get('fields', {}).items():
                fields_info[field_name] = {
                    'type': field_data.get('type'),
                    'string': field_data.get('string'),
                    'required': field_data.get('required', False),
                    'readonly': field_data.get('readonly', False),
                }
            
            existing = Schema.search([
                ('model_name', '=', model_name),
                ('odoo_version', '=', self.version),
            ], limit=1)
            
            vals = {
                'model_name': model_name,
                'odoo_version': self.version,
                'fields_json': json.dumps(fields_info),
                'description': model_data.get('description', ''),
            }
            
            if existing:
                existing.write(vals)
            else:
                Schema.create(vals)

    def action_view_data(self):
        """View parsed data in a popup."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Parsed Data - Odoo {self.version}',
            'res_model': 'ai.odoo.source',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_parsed_data': True},
        }


class AiSourceAnalyzer(models.Model):
    """Analyzer to compare Odoo versions and generate breaking changes."""
    _name = 'ai.source.analyzer'
    _description = 'Source Code Analyzer'

    name = fields.Char('Name', default='Version Comparison', required=True)
    
    from_version_id = fields.Many2one('ai.odoo.source', string='From Version',
        domain="[('state', '=', 'done')]", required=True)
    to_version_id = fields.Many2one('ai.odoo.source', string='To Version',
        domain="[('state', '=', 'done')]", required=True)
    
    from_version = fields.Selection(related='from_version_id.version', store=True)
    to_version = fields.Selection(related='to_version_id.version', store=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('comparing', 'Comparing...'),
        ('review', 'Review Changes'),
        ('done', 'Done'),
    ], default='draft')
    
    # Results
    change_ids = fields.One2many('ai.source.analyzer.change', 'analyzer_id', 
        string='Detected Changes')
    
    # Statistics
    total_changes = fields.Integer(compute='_compute_stats')
    field_changes = fields.Integer(compute='_compute_stats')
    method_changes = fields.Integer(compute='_compute_stats')
    approved_count = fields.Integer(compute='_compute_stats')

    @api.depends('change_ids', 'change_ids.approved')
    def _compute_stats(self):
        for rec in self:
            rec.total_changes = len(rec.change_ids)
            rec.field_changes = len(rec.change_ids.filtered(
                lambda c: c.category in ('field_rename', 'field_remove', 'field_type')))
            rec.method_changes = len(rec.change_ids.filtered(
                lambda c: c.category in ('method_rename', 'method_remove', 'method_signature')))
            rec.approved_count = len(rec.change_ids.filtered('approved'))

    def action_compare(self):
        """Compare two versions and detect breaking changes."""
        self.ensure_one()
        
        if not self.from_version_id.parsed_data or not self.to_version_id.parsed_data:
            raise UserError('Both versions must be analyzed first.')
        
        self.state = 'comparing'
        self.change_ids.unlink()
        
        from_data = json.loads(self.from_version_id.parsed_data)
        to_data = json.loads(self.to_version_id.parsed_data)
        
        changes = []
        
        # Compare models
        from_models = from_data.get('models', {})
        to_models = to_data.get('models', {})
        
        for model_name, from_model in from_models.items():
            to_model = to_models.get(model_name)
            
            if not to_model:
                # Model removed (rare, but possible)
                continue
            
            # Compare fields
            from_fields = from_model.get('fields', {})
            to_fields = to_model.get('fields', {})
            
            for field_name, from_field in from_fields.items():
                to_field = to_fields.get(field_name)
                
                if not to_field:
                    # Field removed - check if renamed
                    possible_rename = self._find_renamed_field(
                        field_name, from_field, to_fields)
                    
                    if possible_rename:
                        changes.append({
                            'analyzer_id': self.id,
                            'category': 'field_rename',
                            'model_name': model_name,
                            'field_name': field_name,
                            'description': f"Field '{field_name}' renamed to '{possible_rename}'",
                            'old_code': f"record.{field_name}",
                            'new_code': f"record.{possible_rename}",
                            'confidence': 'high' if from_field.get('type') == to_fields[possible_rename].get('type') else 'medium',
                        })
                    else:
                        changes.append({
                            'analyzer_id': self.id,
                            'category': 'field_remove',
                            'model_name': model_name,
                            'field_name': field_name,
                            'description': f"Field '{field_name}' removed from {model_name}",
                            'old_code': f"record.{field_name}",
                            'new_code': "# Field no longer exists",
                            'confidence': 'high',
                        })
                
                elif from_field.get('type') != to_field.get('type'):
                    # Field type changed
                    changes.append({
                        'analyzer_id': self.id,
                        'category': 'field_type',
                        'model_name': model_name,
                        'field_name': field_name,
                        'description': f"Field '{field_name}' type changed: {from_field.get('type')} → {to_field.get('type')}",
                        'old_code': f"# {field_name}: {from_field.get('type')}",
                        'new_code': f"# {field_name}: {to_field.get('type')}",
                        'confidence': 'high',
                    })
            
            # Compare methods
            from_methods = from_model.get('methods', {})
            to_methods = to_model.get('methods', {})
            
            for method_name, from_method in from_methods.items():
                # Skip private/magic methods
                if method_name.startswith('_') and not method_name.startswith('_compute'):
                    continue
                
                to_method = to_methods.get(method_name)
                
                if not to_method:
                    # Method removed - check if renamed
                    possible_rename = self._find_renamed_method(
                        method_name, from_method, to_methods)
                    
                    if possible_rename:
                        changes.append({
                            'analyzer_id': self.id,
                            'category': 'method_rename',
                            'model_name': model_name,
                            'method_name': method_name,
                            'description': f"Method '{method_name}' renamed to '{possible_rename}'",
                            'old_code': f"record.{method_name}()",
                            'new_code': f"record.{possible_rename}()",
                            'confidence': 'medium',
                        })
                    else:
                        changes.append({
                            'analyzer_id': self.id,
                            'category': 'method_remove',
                            'model_name': model_name,
                            'method_name': method_name,
                            'description': f"Method '{method_name}' removed from {model_name}",
                            'old_code': f"record.{method_name}()",
                            'new_code': "# Method no longer exists",
                            'confidence': 'medium',
                        })
                
                elif from_method.get('args') != to_method.get('args'):
                    # Method signature changed
                    changes.append({
                        'analyzer_id': self.id,
                        'category': 'method_signature',
                        'model_name': model_name,
                        'method_name': method_name,
                        'description': f"Method '{method_name}' signature changed",
                        'old_code': f"def {method_name}({', '.join(from_method.get('args', []))})",
                        'new_code': f"def {method_name}({', '.join(to_method.get('args', []))})",
                        'confidence': 'high',
                    })
        
        # Bulk create changes
        if changes:
            self.env['ai.source.analyzer.change'].create(changes)
        
        self.state = 'review'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Comparison Complete',
                'message': f"Found {len(changes)} potential breaking changes",
                'type': 'success' if changes else 'info',
            }
        }

    def _find_renamed_field(self, old_name, old_field, new_fields):
        """Try to find if a field was renamed (same type, similar name)."""
        old_type = old_field.get('type')
        
        for new_name, new_field in new_fields.items():
            if new_field.get('type') != old_type:
                continue
            
            # Check for common rename patterns
            # e.g., x_studio_field -> x_field, ref -> memo
            old_clean = old_name.lower().replace('_', '').replace('x', '').replace('studio', '')
            new_clean = new_name.lower().replace('_', '').replace('x', '').replace('studio', '')
            
            if old_clean and new_clean:
                # Similar names (one contains the other)
                if old_clean in new_clean or new_clean in old_clean:
                    return new_name
                
                # Levenshtein-like: same length, few char differences
                if len(old_clean) == len(new_clean):
                    diff = sum(1 for a, b in zip(old_clean, new_clean) if a != b)
                    if diff <= 2:
                        return new_name
        
        return None

    def _find_renamed_method(self, old_name, old_method, new_methods):
        """Try to find if a method was renamed."""
        old_args = old_method.get('args', [])
        
        for new_name, new_method in new_methods.items():
            new_args = new_method.get('args', [])
            
            # Same argument count
            if len(old_args) != len(new_args):
                continue
            
            # Common rename patterns (e.g., post -> action_post)
            if f"action_{old_name}" == new_name:
                return new_name
            if old_name == f"action_{new_name}":
                return new_name
            if old_name.replace('_', '') == new_name.replace('_', ''):
                return new_name
        
        return None

    def action_approve_all(self):
        """Approve all detected changes."""
        self.ensure_one()
        self.change_ids.filtered(lambda c: c.confidence == 'high').write({'approved': True})
        return True

    def action_create_kb_entries(self):
        """Create ai.breaking.change records from approved changes."""
        self.ensure_one()
        
        BreakingChange = self.env['ai.breaking.change']
        created = 0
        
        for change in self.change_ids.filtered('approved'):
            # Check for duplicate
            existing = BreakingChange.search([
                ('from_version', '=', self.from_version),
                ('to_version', '=', self.to_version),
                ('category', '=', change.category),
                ('model_name', '=', change.model_name),
                ('field_name', '=', change.field_name),
                ('method_name', '=', change.method_name),
            ], limit=1)
            
            if existing:
                continue
            
            BreakingChange.create({
                'from_version': self.from_version,
                'to_version': self.to_version,
                'category': change.category,
                'model_name': change.model_name,
                'field_name': change.field_name,
                'method_name': change.method_name,
                'description': change.description,
                'old_code': change.old_code,
                'new_code': change.new_code,
                'source': 'learned',
                'verified': True,
            })
            created += 1
        
        self.state = 'done'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'KB Updated',
                'message': f"Created {created} breaking change entries",
                'type': 'success',
            }
        }


class AiSourceAnalyzerChange(models.Model):
    """Detected change between versions."""
    _name = 'ai.source.analyzer.change'
    _description = 'Detected Change'
    _order = 'category, model_name, field_name'

    analyzer_id = fields.Many2one('ai.source.analyzer', ondelete='cascade')
    
    category = fields.Selection([
        ('field_rename', 'Field Renamed'),
        ('field_remove', 'Field Removed'),
        ('field_type', 'Field Type Changed'),
        ('method_rename', 'Method Renamed'),
        ('method_remove', 'Method Removed'),
        ('method_signature', 'Method Signature'),
    ], required=True)
    
    model_name = fields.Char('Model')
    field_name = fields.Char('Field')
    method_name = fields.Char('Method')
    
    description = fields.Text('Description')
    old_code = fields.Text('Old Code')
    new_code = fields.Text('New Code')
    
    confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], default='medium')
    
    approved = fields.Boolean('Approved', default=False)
    rejected = fields.Boolean('Rejected', default=False)

    def action_approve(self):
        self.approved = True
        self.rejected = False

    def action_reject(self):
        self.approved = False
        self.rejected = True


# =============================================================================
# PARSER (Pure Python, no Odoo dependencies)
# =============================================================================

class OdooSourceParser:
    """
    Parse Odoo source code and extract metadata.
    
    This is a standalone class that uses Python's AST module to parse
    Odoo model definitions without actually importing them.
    """
    
    def __init__(self, source_path, version):
        self.source_path = Path(source_path)
        self.version = version
        self.result = {
            'version': version,
            'models': {},
            'stats': {'modules': 0, 'models': 0, 'fields': 0, 'methods': 0},
        }
    
    def parse_all(self):
        """Parse all modules in the source path."""
        if not self.source_path.exists():
            raise ValueError(f"Path does not exist: {self.source_path}")
        
        # Find all module directories (have __manifest__.py or __openerp__.py)
        for manifest in self.source_path.rglob('__manifest__.py'):
            module_path = manifest.parent
            self._parse_module(module_path)
        
        # Also check __openerp__.py for older versions
        for manifest in self.source_path.rglob('__openerp__.py'):
            module_path = manifest.parent
            if not (module_path / '__manifest__.py').exists():
                self._parse_module(module_path)
        
        return self.result
    
    def _parse_module(self, module_path):
        """Parse a single Odoo module."""
        module_name = module_path.name
        self.result['stats']['modules'] += 1
        
        # Find all Python files in models/ directory
        models_dir = module_path / 'models'
        if models_dir.exists():
            for py_file in models_dir.glob('*.py'):
                if py_file.name.startswith('_'):
                    continue
                self._parse_python_file(py_file, module_name)
        
        # Also check root level for models (some modules don't use models/ dir)
        for py_file in module_path.glob('*.py'):
            if py_file.name.startswith('_'):
                continue
            if py_file.name in ('__init__.py', '__manifest__.py', '__openerp__.py'):
                continue
            self._parse_python_file(py_file, module_name)
    
    def _parse_python_file(self, file_path, module_name):
        """Parse a Python file and extract model definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    model_info = self._parse_class(node, module_name)
                    if model_info:
                        model_name = model_info['name']
                        
                        # Merge with existing (for _inherit cases)
                        if model_name in self.result['models']:
                            existing = self.result['models'][model_name]
                            existing['fields'].update(model_info['fields'])
                            existing['methods'].update(model_info['methods'])
                        else:
                            self.result['models'][model_name] = model_info
                            self.result['stats']['models'] += 1
                        
                        self.result['stats']['fields'] += len(model_info['fields'])
                        self.result['stats']['methods'] += len(model_info['methods'])
        
        except SyntaxError as e:
            _logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            _logger.warning(f"Error parsing {file_path}: {e}")
    
    def _parse_class(self, node, module_name):
        """Parse a class definition to extract Odoo model info."""
        # Check if it's an Odoo model (has _name or _inherit)
        model_name = None
        model_inherit = None
        description = None
        
        fields = {}
        methods = {}
        
        for item in node.body:
            # Look for _name = '...'
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == '_name' and isinstance(item.value, ast.Constant):
                            model_name = item.value.value
                        elif target.id == '_inherit':
                            if isinstance(item.value, ast.Constant):
                                model_inherit = item.value.value
                            elif isinstance(item.value, ast.List):
                                # _inherit = ['a', 'b']
                                model_inherit = [
                                    e.value for e in item.value.elts 
                                    if isinstance(e, ast.Constant)
                                ]
                        elif target.id == '_description' and isinstance(item.value, ast.Constant):
                            description = item.value.value
                        
                        # Parse field definitions
                        elif isinstance(item.value, ast.Call):
                            field_info = self._parse_field(target.id, item.value)
                            if field_info:
                                fields[target.id] = field_info
            
            # Parse methods
            elif isinstance(item, ast.FunctionDef):
                method_info = self._parse_method(item)
                if method_info:
                    methods[item.name] = method_info
        
        # Use _inherit as model_name if no _name
        if not model_name and model_inherit:
            if isinstance(model_inherit, str):
                model_name = model_inherit
            elif isinstance(model_inherit, list) and model_inherit:
                model_name = model_inherit[0]
        
        if not model_name:
            return None
        
        return {
            'name': model_name,
            'class_name': node.name,
            'module': module_name,
            'description': description,
            'inherit': model_inherit,
            'fields': fields,
            'methods': methods,
        }
    
    def _parse_field(self, field_name, call_node):
        """Parse a field definition like: name = fields.Char('Name', required=True)"""
        if not isinstance(call_node.func, ast.Attribute):
            return None
        
        # Check if it's fields.Xxx
        if isinstance(call_node.func.value, ast.Name):
            if call_node.func.value.id != 'fields':
                return None
        elif isinstance(call_node.func.value, ast.Attribute):
            # Handle odoo.fields.Xxx or models.fields.Xxx
            if call_node.func.value.attr != 'fields':
                return None
        else:
            return None
        
        field_type = call_node.func.attr
        
        # Skip non-field attributes
        if field_type in ('Model', 'AbstractModel', 'TransientModel'):
            return None
        
        field_info = {
            'type': field_type,
            'string': None,
            'required': False,
            'readonly': False,
            'compute': None,
            'related': None,
        }
        
        # Parse positional args (usually string label)
        if call_node.args:
            first_arg = call_node.args[0]
            if isinstance(first_arg, ast.Constant):
                field_info['string'] = first_arg.value
        
        # Parse keyword args
        for kw in call_node.keywords:
            if kw.arg == 'string' and isinstance(kw.value, ast.Constant):
                field_info['string'] = kw.value.value
            elif kw.arg == 'required' and isinstance(kw.value, ast.Constant):
                field_info['required'] = kw.value.value
            elif kw.arg == 'readonly' and isinstance(kw.value, ast.Constant):
                field_info['readonly'] = kw.value.value
            elif kw.arg == 'compute' and isinstance(kw.value, ast.Constant):
                field_info['compute'] = kw.value.value
            elif kw.arg == 'related' and isinstance(kw.value, ast.Constant):
                field_info['related'] = kw.value.value
            elif kw.arg == 'comodel_name' and isinstance(kw.value, ast.Constant):
                field_info['comodel'] = kw.value.value
        
        return field_info
    
    def _parse_method(self, node):
        """Parse a method definition."""
        # Get decorators
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{dec.value.id}.{dec.attr}" if isinstance(dec.value, ast.Name) else dec.attr)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)
                elif isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
        
        # Get arguments
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        
        return {
            'name': node.name,
            'args': args,
            'decorators': decorators,
            'is_api_model': 'api.model' in decorators,
            'is_api_depends': any('depends' in d for d in decorators),
            'is_api_onchange': any('onchange' in d for d in decorators),
            'is_api_constrains': any('constrains' in d for d in decorators),
        }
