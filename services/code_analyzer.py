# -*- coding: utf-8 -*-

import os
import ast
import re
import logging
from lxml import etree
from typing import Dict, List, Any, Optional

_logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """
    Enhanced service for analyzing Odoo module code.
    
    Supports THREE modes for source code access:
    1. GIT: Fetch from GitHub/GitLab/Bitbucket repository (PRIMARY)
    2. LOCAL: Read from installed module path (if accessible on server)
    3. UPLOAD: Parse uploaded source files (via specification)
    
    Falls back to database-only analysis if source code is not available.
    """
    
    def __init__(self, env):
        self.env = env
    
    def analyze_module(self, module_name: str, source_mode: str = 'auto') -> Dict[str, str]:
        """
        Analyze an Odoo module and return summary information
        
        Args:
            module_name: Technical name of the module
            source_mode: 'auto', 'git', 'local', or 'database_only'
        """
        result = self.analyze_module_full(module_name, source_mode)
        return {
            'models': result.get('models_summary', ''),
            'views': result.get('views_summary', ''),
            'fields': result.get('fields_summary', ''),
            'buttons': result.get('buttons_summary', ''),
        }
    
    def analyze_module_full(self, module_name: str, source_mode: str = 'auto') -> Dict[str, Any]:
        """
        Full analysis of an Odoo module including source code
        
        Args:
            module_name: Technical name of the module
            source_mode: 
                - 'auto': Try git first, then local, then database only
                - 'git': Fetch from configured Git repository
                - 'local': Read from local file system
                - 'database_only': Only use database metadata
        """
        result = {
            'models_raw': {}, 'views_raw': {}, 'fields_raw': {}, 'buttons_raw': {},
            'methods_raw': {}, 'validations_raw': [], 'error_messages_raw': [],
            'onchange_raw': [], 'constraints_raw': [], 'computed_fields_raw': [], 'workflows_raw': [],
            'models_summary': '', 'views_summary': '', 'fields_summary': '', 'buttons_summary': '',
            'source_mode_used': None, 'model_count': 0, 'view_count': 0, 'field_count': 0, 'button_count': 0,
        }
        
        try:
            _logger.info(f"Analyzing module: {module_name} (mode: {source_mode})")
            
            # 1. Database analysis (always available)
            models_data = self._analyze_models_from_db(module_name)
            result['models_raw'] = models_data
            result['model_count'] = len(models_data)
            
            fields_data = self._analyze_fields_from_db(module_name)
            result['fields_raw'] = fields_data
            result['field_count'] = sum(len(f) for f in fields_data.values())
            
            views_data = self._analyze_views_from_db(module_name)
            result['views_raw'] = views_data
            result['view_count'] = len(views_data)
            
            buttons_data = self._extract_buttons_from_views(views_data)
            result['buttons_raw'] = buttons_data
            result['button_count'] = len(buttons_data)
            
            # 2. Source code analysis
            source_analysis = None
            if source_mode != 'database_only':
                source_analysis = self._get_source_analysis(module_name, source_mode)
                if source_analysis:
                    result['methods_raw'] = source_analysis.get('methods', {})
                    result['validations_raw'] = source_analysis.get('validations', [])
                    result['error_messages_raw'] = source_analysis.get('error_messages', [])
                    result['onchange_raw'] = source_analysis.get('onchange', [])
                    result['constraints_raw'] = source_analysis.get('constraints', [])
                    result['computed_fields_raw'] = source_analysis.get('computed_fields', [])
                    result['workflows_raw'] = source_analysis.get('workflows', [])
                    result['source_mode_used'] = source_analysis.get('source_mode')
            
            # 3. Generate summaries
            result['models_summary'] = self._format_models_summary(models_data, source_analysis)
            result['views_summary'] = self._format_views_summary(views_data)
            result['fields_summary'] = self._format_fields_summary(fields_data, source_analysis)
            result['buttons_summary'] = self._format_buttons_summary(buttons_data, source_analysis)
            
        except Exception as e:
            _logger.error(f"Module analysis error: {str(e)}")
            raise
        
        return result
    
    # ==================== SOURCE CODE FETCHING ====================
    
    def _get_source_analysis(self, module_name: str, source_mode: str) -> Optional[Dict]:
        """Get source code analysis based on configured mode"""
        if source_mode == 'auto':
            # Try git first, then local
            for mode, method in [('git', self._analyze_from_git), ('local', self._analyze_from_local)]:
                result = method(module_name)
                if result:
                    result['source_mode'] = mode
                    return result
            _logger.info(f"No source code available for {module_name}")
            return None
        elif source_mode == 'git':
            result = self._analyze_from_git(module_name)
            if result: result['source_mode'] = 'git'
            return result
        elif source_mode == 'local':
            result = self._analyze_from_local(module_name)
            if result: result['source_mode'] = 'local'
            return result
        return None
    
    def _analyze_from_git(self, module_name: str) -> Optional[Dict]:
        """Analyze source code fetched from Git repository"""
        try:
            ModuleSource = self.env['qa.module.source'].sudo()
            source_config = ModuleSource.search([('module_name', '=', module_name)], limit=1)
            
            if not source_config:
                _logger.debug(f"No Git repository configured for: {module_name}")
                return None
            
            source_data = source_config.get_cached_source()
            if not source_data or not source_data.get('python_files'):
                return None
            
            return self._analyze_source_content(source_data)
        except Exception as e:
            _logger.warning(f"Git source analysis failed for {module_name}: {e}")
            return None
    
    def _analyze_from_local(self, module_name: str) -> Optional[Dict]:
        """Analyze source code from local file system"""
        try:
            from odoo.modules.module import get_module_path
            module_path = get_module_path(module_name)
            if not module_path or not os.path.exists(module_path):
                return None
            return self._analyze_source_path(module_path)
        except Exception as e:
            _logger.debug(f"Local source analysis failed for {module_name}: {e}")
            return None
    
    def analyze_from_upload(self, python_files: Dict[str, str], xml_files: Dict[str, str] = None) -> Dict:
        """Analyze source code from uploaded files"""
        source_data = {'python_files': python_files, 'xml_files': xml_files or {}}
        result = self._analyze_source_content(source_data)
        result['source_mode'] = 'upload'
        return result
    
    # ==================== SOURCE CODE PARSING ====================
    
    def _analyze_source_content(self, source_data: Dict) -> Dict:
        """Analyze source code from content dictionary (Git or uploaded files)"""
        result = {
            'methods': {}, 'validations': [], 'error_messages': [],
            'onchange': [], 'constraints': [], 'computed_fields': [], 'workflows': [],
        }
        for filename, content in source_data.get('python_files', {}).items():
            self._parse_python_content(content, filename, result)
        for filename, content in source_data.get('xml_files', {}).items():
            self._parse_xml_content(content, filename, result)
        return result
    
    def _analyze_source_path(self, module_path: str) -> Dict:
        """Analyze source code from local file path"""
        result = {
            'methods': {}, 'validations': [], 'error_messages': [],
            'onchange': [], 'constraints': [], 'computed_fields': [], 'workflows': [],
        }
        
        # Parse Python files in models/
        models_dir = os.path.join(module_path, 'models')
        if os.path.exists(models_dir):
            for filename in os.listdir(models_dir):
                if filename.endswith('.py') and not filename.startswith('__'):
                    filepath = os.path.join(models_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self._parse_python_content(f.read(), filename, result)
        
        # Parse XML files in views/
        views_dir = os.path.join(module_path, 'views')
        if os.path.exists(views_dir):
            for filename in os.listdir(views_dir):
                if filename.endswith('.xml'):
                    filepath = os.path.join(views_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self._parse_xml_content(f.read(), filename, result)
        
        return result
    
    def _parse_python_content(self, content: str, filename: str, result: Dict) -> None:
        """Parse Python source code using AST"""
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._analyze_class(node, content, result)
        except Exception as e:
            _logger.warning(f"Could not parse {filename}: {e}")
    
    def _parse_xml_content(self, content: str, filename: str, result: Dict) -> None:
        """Parse XML content for workflow states"""
        try:
            root = etree.fromstring(content.encode('utf-8'))
            for field in root.xpath('//field[@widget="statusbar"]'):
                if field.get('name') == 'state':
                    statusbar_visible = field.get('statusbar_visible', '')
                    if statusbar_visible:
                        states = [s.strip() for s in statusbar_visible.split(',')]
                        result['workflows'].append({'field': 'state', 'states': states})
        except Exception as e:
            _logger.debug(f"Could not parse XML {filename}: {e}")
    
    def _analyze_class(self, class_node: ast.ClassDef, source: str, result: Dict) -> None:
        """Analyze a class definition to extract Odoo model info"""
        model_name = None
        
        # Find _name or _inherit
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == '_name' and isinstance(node.value, ast.Constant):
                            model_name = node.value.value
                            break
                        elif target.id == '_inherit':
                            if isinstance(node.value, ast.Constant):
                                model_name = node.value.value
                            elif isinstance(node.value, ast.List) and node.value.elts:
                                if isinstance(node.value.elts[0], ast.Constant):
                                    model_name = node.value.elts[0].value
        
        if not model_name:
            return
        
        if model_name not in result['methods']:
            result['methods'][model_name] = []
        
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                self._analyze_method(node, model_name, source, result)
            elif isinstance(node, ast.Assign):
                self._analyze_field_definition(node, model_name, result)
    
    def _analyze_method(self, method_node: ast.FunctionDef, model_name: str, source: str, result: Dict) -> None:
        """Analyze a method to extract logic, decorators, validations"""
        method_name = method_node.name
        if method_name.startswith('__'):
            return
        
        decorators = [self._get_decorator_info(d) for d in method_node.decorator_list]
        decorators = [d for d in decorators if d]
        docstring = ast.get_docstring(method_node) or ''
        
        method_info = {
            'name': method_name, 'docstring': docstring, 'decorators': decorators,
            'is_action': method_name.startswith('action_'),
            'is_compute': any(d.get('name') == 'depends' for d in decorators),
            'is_onchange': any(d.get('name') == 'onchange' for d in decorators),
            'is_constrains': any(d.get('name') == 'constrains' for d in decorators),
        }
        
        # Extract error messages and validations
        result['error_messages'].extend(self._extract_error_messages(method_node, model_name, method_name))
        result['validations'].extend(self._extract_validations(method_node, model_name, method_name))
        
        # Handle decorators
        for dec in decorators:
            if dec.get('name') == 'onchange':
                result['onchange'].append({
                    'model': model_name, 'method': method_name,
                    'fields': dec.get('args', []), 'docstring': docstring,
                })
            elif dec.get('name') == 'constrains':
                constraint_msg = self._extract_constraint_message(method_node)
                result['constraints'].append({
                    'model': model_name, 'method': method_name,
                    'fields': dec.get('args', []), 'message': constraint_msg,
                })
            elif dec.get('name') == 'depends':
                result['computed_fields'].append({
                    'model': model_name, 'method': method_name,
                    'depends': dec.get('args', []), 'docstring': docstring,
                })
        
        result['methods'][model_name].append(method_info)
    
    def _get_decorator_info(self, dec_node) -> Optional[Dict]:
        """Extract decorator name and arguments"""
        if isinstance(dec_node, ast.Name):
            return {'name': dec_node.id, 'args': []}
        elif isinstance(dec_node, ast.Attribute):
            return {'name': dec_node.attr, 'args': []}
        elif isinstance(dec_node, ast.Call):
            if isinstance(dec_node.func, ast.Attribute):
                name = dec_node.func.attr
            elif isinstance(dec_node.func, ast.Name):
                name = dec_node.func.id
            else:
                return None
            args = [arg.value for arg in dec_node.args if isinstance(arg, ast.Constant)]
            return {'name': name, 'args': args}
        return None
    
    def _extract_error_messages(self, method_node: ast.FunctionDef, model_name: str, method_name: str) -> List[Dict]:
        """Extract UserError and ValidationError messages"""
        errors = []
        for node in ast.walk(method_node):
            if isinstance(node, ast.Raise) and node.exc and isinstance(node.exc, ast.Call):
                func = node.exc.func
                error_type = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
                if error_type in ['UserError', 'ValidationError', 'Warning']:
                    message = self._extract_string_from_call(node.exc)
                    if message:
                        errors.append({'model': model_name, 'method': method_name, 'type': error_type, 'message': message})
        return errors
    
    def _extract_string_from_call(self, call_node: ast.Call) -> Optional[str]:
        """Extract string argument from a function call"""
        if not call_node.args:
            return None
        arg = call_node.args[0]
        if isinstance(arg, ast.Constant):
            return str(arg.value)
        elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == '_':
            if arg.args and isinstance(arg.args[0], ast.Constant):
                return str(arg.args[0].value)
        elif isinstance(arg, ast.JoinedStr):
            parts = [str(v.value) if isinstance(v, ast.Constant) else "{...}" for v in arg.values]
            return ''.join(parts)
        return None
    
    def _extract_validations(self, method_node: ast.FunctionDef, model_name: str, method_name: str) -> List[Dict]:
        """Extract validation conditions (if statements before raise)"""
        validations = []
        for node in ast.walk(method_node):
            if isinstance(node, ast.If):
                if any(isinstance(n, ast.Raise) for n in ast.walk(node)):
                    condition = self._simplify_condition(node.test)
                    if condition:
                        validations.append({'model': model_name, 'method': method_name, 'condition': condition})
        return validations
    
    def _simplify_condition(self, test_node) -> Optional[str]:
        """Convert AST condition to readable string"""
        try:
            if isinstance(test_node, ast.Compare):
                left = self._node_to_string(test_node.left)
                op = self._op_to_string(test_node.ops[0])
                right = self._node_to_string(test_node.comparators[0])
                return f"{left} {op} {right}"
            elif isinstance(test_node, ast.UnaryOp) and isinstance(test_node.op, ast.Not):
                return f"not {self._simplify_condition(test_node.operand)}"
            elif isinstance(test_node, ast.BoolOp):
                op = 'and' if isinstance(test_node.op, ast.And) else 'or'
                return f" {op} ".join(filter(None, [self._simplify_condition(v) for v in test_node.values]))
            elif isinstance(test_node, (ast.Attribute, ast.Name)):
                return self._node_to_string(test_node)
        except:
            pass
        return None
    
    def _node_to_string(self, node) -> str:
        if isinstance(node, ast.Constant): return repr(node.value)
        elif isinstance(node, ast.Name): return node.id
        elif isinstance(node, ast.Attribute): return f"{self._node_to_string(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript): return f"{self._node_to_string(node.value)}[...]"
        return "?"
    
    def _op_to_string(self, op) -> str:
        return {ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=',
                ast.Is: 'is', ast.IsNot: 'is not', ast.In: 'in', ast.NotIn: 'not in'}.get(type(op), '?')
    
    def _extract_constraint_message(self, method_node: ast.FunctionDef) -> Optional[str]:
        for node in ast.walk(method_node):
            if isinstance(node, ast.Raise) and node.exc and isinstance(node.exc, ast.Call):
                return self._extract_string_from_call(node.exc)
        return None
    
    def _analyze_field_definition(self, assign_node: ast.Assign, model_name: str, result: Dict) -> None:
        """Analyze field definitions for computed fields"""
        for target in assign_node.targets:
            if isinstance(target, ast.Name) and isinstance(assign_node.value, ast.Call):
                field_name = target.id
                for keyword in assign_node.value.keywords:
                    if keyword.arg == 'compute' and isinstance(keyword.value, ast.Constant):
                        depends = []
                        for kw in assign_node.value.keywords:
                            if kw.arg == 'depends' and isinstance(kw.value, ast.List):
                                depends = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                        result['computed_fields'].append({
                            'model': model_name, 'field': field_name,
                            'compute_method': keyword.value.value, 'depends': depends
                        })
    
    # ==================== DATABASE ANALYSIS ====================
    
    def _analyze_models_from_db(self, module_name: str) -> Dict[str, Any]:
        models_data = {}
        prefixes = [module_name, module_name.replace('_', '.')]
        IrModel = self.env['ir.model'].sudo()
        domain = ['|', ('modules', 'ilike', module_name)] + ['|'] * (len(prefixes) - 1) + [('model', 'like', f'{p}%') for p in prefixes]
        
        for model in IrModel.search(domain, limit=50):
            try:
                model_obj = self.env[model.model].sudo()
                models_data[model.model] = {
                    'name': model.name, 'model': model.model, 'description': model.info or '',
                    'transient': model.transient, 'fields': list(model_obj._fields.keys()),
                }
            except Exception as e:
                _logger.debug(f"Could not analyze model {model.model}: {e}")
        return models_data
    
    def _analyze_fields_from_db(self, module_name: str) -> Dict[str, List[Dict]]:
        fields_data = {}
        models_data = self._analyze_models_from_db(module_name)
        
        for model_name in models_data.keys():
            try:
                model_obj = self.env[model_name].sudo()
                fields_list = []
                for field_name, field in model_obj._fields.items():
                    if field_name.startswith('_'): continue
                    field_info = {
                        'name': field_name, 'type': field.type, 'string': field.string,
                        'required': field.required, 'readonly': field.readonly, 'help': field.help or '',
                    }
                    if field.type in ('many2one', 'one2many', 'many2many'):
                        field_info['relation'] = getattr(field, 'comodel_name', '')
                    if field.type == 'selection':
                        selection = field.selection
                        if callable(selection):
                            try: selection = selection(model_obj)
                            except: selection = []
                        field_info['selection'] = selection
                    fields_list.append(field_info)
                fields_data[model_name] = fields_list
            except Exception as e:
                _logger.debug(f"Could not analyze fields for {model_name}: {e}")
        return fields_data
    
    def _analyze_views_from_db(self, module_name: str) -> Dict[str, Any]:
        views_data = {}
        IrUIView = self.env['ir.ui.view'].sudo()
        models_data = self._analyze_models_from_db(module_name)
        
        for model_name in models_data.keys():
            for view in IrUIView.search([('model', '=', model_name), ('type', 'in', ['form', 'tree', 'search', 'kanban'])], limit=10):
                try:
                    views_data[view.xml_id or str(view.id)] = {
                        'name': view.name, 'model': view.model, 'type': view.type, 'arch': view.arch,
                        'fields': self._extract_fields_from_arch(view.arch),
                        'buttons': self._extract_buttons_from_arch(view.arch),
                    }
                except Exception as e:
                    _logger.debug(f"Could not analyze view {view.name}: {e}")
        return views_data
    
    def _extract_fields_from_arch(self, arch: str) -> List[str]:
        fields = []
        try:
            root = etree.fromstring(arch.encode('utf-8'))
            for field in root.xpath('//field[@name]'):
                if field.get('name') not in fields:
                    fields.append(field.get('name'))
        except: pass
        return fields
    
    def _extract_buttons_from_arch(self, arch: str) -> List[Dict]:
        buttons = []
        try:
            root = etree.fromstring(arch.encode('utf-8'))
            for button in root.xpath('//button[@name]'):
                buttons.append({
                    'name': button.get('name'), 'string': button.get('string', ''),
                    'type': button.get('type', 'object'), 'class': button.get('class', ''),
                    'states': button.get('states', ''), 'invisible': button.get('invisible', ''),
                })
        except: pass
        return buttons
    
    def _extract_buttons_from_views(self, views_data: Dict) -> List[Dict]:
        buttons, seen = [], set()
        for view_id, view_info in views_data.items():
            for button in view_info.get('buttons', []):
                key = (button.get('name'), button.get('string'))
                if key not in seen:
                    seen.add(key)
                    buttons.append({**button, 'view': view_id, 'model': view_info.get('model')})
        return buttons
    
    # ==================== FORMATTING ====================
    
    def _format_models_summary(self, models_data: Dict, source_analysis: Dict = None) -> str:
        lines = ["## Available Models\n"]
        for model_name, info in models_data.items():
            lines.append(f"### {info.get('name', model_name)}")
            lines.append(f"- Technical Name: `{model_name}`")
            if info.get('description'): lines.append(f"- Description: {info['description']}")
            lines.append(f"- Fields: {len(info.get('fields', []))}")
            
            if source_analysis and model_name in source_analysis.get('methods', {}):
                action_methods = [m for m in source_analysis['methods'][model_name] if m.get('is_action')]
                if action_methods:
                    lines.append(f"\n**Action Methods:**")
                    for method in action_methods[:5]:
                        doc = method.get('docstring', '')[:100]
                        lines.append(f"- `{method['name']}()`: {doc or 'No description'}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_fields_summary(self, fields_data: Dict, source_analysis: Dict = None) -> str:
        lines = ["## Available Fields\n"]
        for model_name, fields in fields_data.items():
            lines.append(f"### {model_name}")
            
            for label, filter_fn in [
                ("Required Fields", lambda f: f.get('required')),
                ("Relational Fields", lambda f: f.get('type') in ('many2one', 'one2many', 'many2many')),
                ("Selection Fields", lambda f: f.get('type') == 'selection'),
            ]:
                filtered = [f for f in fields if filter_fn(f)][:10]
                if filtered:
                    lines.append(f"\n**{label}:**")
                    for f in filtered:
                        if f.get('type') in ('many2one', 'one2many', 'many2many'):
                            lines.append(f"- `{f['name']}` ({f['type']} → {f.get('relation', '')})")
                        elif f.get('type') == 'selection' and f.get('selection'):
                            options = ', '.join([f"'{s[0]}'" for s in f['selection'][:5]])
                            lines.append(f"- `{f['name']}`: [{options}]")
                        else:
                            lines.append(f"- `{f['name']}` ({f['type']}): {f.get('string', '')}")
            
            if source_analysis:
                computed = [c for c in source_analysis.get('computed_fields', []) if c.get('model') == model_name]
                if computed:
                    lines.append("\n**Computed Fields:**")
                    for c in computed[:5]:
                        depends = ', '.join(c.get('depends', []))
                        lines.append(f"- `{c.get('field', c.get('method'))}` depends on: [{depends}]")
            lines.append("")
        return "\n".join(lines)
    
    def _format_views_summary(self, views_data: Dict) -> str:
        lines = ["## Available Views\n"]
        for view_id, info in views_data.items():
            lines.append(f"### {info.get('name', view_id)}")
            lines.append(f"- Model: `{info.get('model')}`")
            lines.append(f"- Type: {info.get('type')}")
            field_list = info.get('fields', [])[:10]
            lines.append(f"- Fields: {', '.join(field_list)}")
            if len(info.get('fields', [])) > 10:
                lines.append(f"  ... and {len(info['fields']) - 10} more")
            lines.append("")
        return "\n".join(lines)
    
    def _format_buttons_summary(self, buttons_data: List, source_analysis: Dict = None) -> str:
        lines = ["## Available Buttons/Actions\n"]
        
        error_lookup, validation_lookup = {}, {}
        if source_analysis:
            for error in source_analysis.get('error_messages', []):
                key = (error.get('model'), error.get('method'))
                error_lookup.setdefault(key, []).append(error.get('message'))
            for validation in source_analysis.get('validations', []):
                key = (validation.get('model'), validation.get('method'))
                validation_lookup.setdefault(key, []).append(validation.get('condition'))
        
        for button in buttons_data:
            name, string, model = button.get('name'), button.get('string', ''), button.get('model', '')
            lines.append(f"### {string or name}")
            lines.append(f"- Action: `{name}` (type: {button.get('type', 'object')})")
            lines.append(f"- Model: `{model}`")
            if button.get('states'): lines.append(f"- Available in states: {button['states']}")
            lines.append(f"- Locator: `//button[@name='{name}']`")
            
            key = (model, name)
            if key in validation_lookup:
                lines.append(f"\n**Validations:**")
                for condition in validation_lookup[key][:3]:
                    lines.append(f"- Checks: `{condition}`")
            if key in error_lookup:
                lines.append(f"\n**Possible Errors:**")
                for message in error_lookup[key][:3]:
                    lines.append(f"- \"{message}\"")
            
            if source_analysis and model in source_analysis.get('methods', {}):
                for method in source_analysis['methods'][model]:
                    if method['name'] == name and method.get('docstring'):
                        lines.append(f"\n**Description:** {method['docstring'][:200]}")
                        break
            lines.append("")
        
        # Add constraints and onchange info
        if source_analysis:
            if source_analysis.get('constraints'):
                lines.append("\n## Validation Constraints\n")
                for c in source_analysis['constraints']:
                    lines.append(f"- **{c.get('model')}.{c.get('method')}** on `{', '.join(c.get('fields', []))}`")
                    if c.get('message'): lines.append(f"  - Error: \"{c['message']}\"")
            
            if source_analysis.get('onchange'):
                lines.append("\n## Onchange Behaviors\n")
                for o in source_analysis['onchange']:
                    lines.append(f"- When `{', '.join(o.get('fields', []))}` changes → `{o.get('method')}()`")
                    if o.get('docstring'): lines.append(f"  - Effect: {o['docstring'][:100]}")
        
        return "\n".join(lines)
