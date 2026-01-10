# -*- coding: utf-8 -*-

from odoo import models, api
import os
import re
import ast
import json
import tempfile
import shutil
import subprocess
import logging

_logger = logging.getLogger(__name__)


class QACodeScanner(models.AbstractModel):
    _name = 'qa.code.scanner'
    _description = 'Code Scanner Service'

    @api.model
    def fetch_repository(self, repository, branch='main'):
        """Clone or fetch repository and return path"""
        # Create temp directory for repo
        temp_dir = tempfile.mkdtemp(prefix='qa_scan_')
        
        try:
            # Build clone URL with authentication
            clone_url = repository.repo_url
            if repository.auth_type == 'token' and repository.access_token:
                # Insert token into URL
                if 'github.com' in clone_url:
                    clone_url = clone_url.replace('https://', f'https://{repository.access_token}@')
                elif 'gitlab' in clone_url:
                    clone_url = clone_url.replace('https://', f'https://oauth2:{repository.access_token}@')
                elif 'bitbucket' in clone_url:
                    clone_url = clone_url.replace('https://', f'https://x-token-auth:{repository.access_token}@')
            
            # Clone repository
            _logger.info(f"Cloning repository to {temp_dir}")
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', '--branch', branch, clone_url, temp_dir],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            # Get commit info
            commit_result = subprocess.run(
                ['git', 'log', '-1', '--format=%H|%s'],
                cwd=temp_dir,
                capture_output=True,
                text=True
            )
            
            commit_info = {'hash': '', 'message': ''}
            if commit_result.returncode == 0:
                parts = commit_result.stdout.strip().split('|', 1)
                commit_info = {
                    'hash': parts[0] if parts else '',
                    'message': parts[1] if len(parts) > 1 else ''
                }
            
            return temp_dir, commit_info
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise

    @api.model
    def discover_modules(self, repo_path):
        """Find all Odoo modules in repository"""
        modules = []
        
        # Walk directory looking for __manifest__.py
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common non-module dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__']]
            
            if '__manifest__.py' in files:
                module_path = root
                module_name = os.path.basename(module_path)
                rel_path = os.path.relpath(module_path, repo_path)
                
                # Parse manifest
                manifest_data = self._parse_manifest(os.path.join(module_path, '__manifest__.py'))
                
                # Count models and views
                model_count = self._count_models(module_path)
                view_count = self._count_views(module_path)
                
                modules.append({
                    'name': module_name,
                    'display_name': manifest_data.get('name', module_name),
                    'version': manifest_data.get('version', ''),
                    'path': rel_path,
                    'depends': manifest_data.get('depends', []),
                    'model_count': model_count,
                    'view_count': view_count,
                })
        
        return modules

    @api.model
    def _parse_manifest(self, manifest_path):
        """Parse __manifest__.py file"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Safely evaluate the manifest dict
            return ast.literal_eval(content)
        except Exception as e:
            _logger.warning(f"Failed to parse manifest {manifest_path}: {e}")
            return {}

    @api.model
    def _count_models(self, module_path):
        """Count model definitions in module"""
        count = 0
        models_dir = os.path.join(module_path, 'models')
        
        if os.path.isdir(models_dir):
            for py_file in self._find_python_files(models_dir):
                count += self._count_model_classes(py_file)
        
        # Also check root for models
        for py_file in self._find_python_files(module_path, recursive=False):
            count += self._count_model_classes(py_file)
        
        return count

    @api.model
    def _count_model_classes(self, py_file):
        """Count Model classes in a Python file"""
        count = 0
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Simple regex to find _name = 'xxx' patterns
            count = len(re.findall(r"_name\s*=\s*['\"][\w.]+['\"]", content))
        except:
            pass
        return count

    @api.model
    def _count_views(self, module_path):
        """Count view definitions in module"""
        count = 0
        views_dir = os.path.join(module_path, 'views')
        
        if os.path.isdir(views_dir):
            for xml_file in self._find_xml_files(views_dir):
                count += self._count_view_records(xml_file)
        
        return count

    @api.model
    def _count_view_records(self, xml_file):
        """Count ir.ui.view records in XML file"""
        count = 0
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Count view records
            count = len(re.findall(r'model=["\']ir\.ui\.view["\']', content))
        except:
            pass
        return count

    @api.model
    def _find_python_files(self, directory, recursive=True):
        """Find all Python files in directory"""
        files = []
        if recursive:
            for root, dirs, filenames in os.walk(directory):
                dirs[:] = [d for d in dirs if not d.startswith('__')]
                for f in filenames:
                    if f.endswith('.py') and not f.startswith('__'):
                        files.append(os.path.join(root, f))
        else:
            for f in os.listdir(directory):
                if f.endswith('.py') and not f.startswith('__'):
                    files.append(os.path.join(directory, f))
        return files

    @api.model
    def _find_xml_files(self, directory):
        """Find all XML files in directory"""
        files = []
        for root, dirs, filenames in os.walk(directory):
            for f in filenames:
                if f.endswith('.xml'):
                    files.append(os.path.join(root, f))
        return files

    @api.model
    def analyze_module(self, module_path, module_name):
        """Analyze module and extract model information"""
        analysis = {
            'name': module_name,
            'models': []
        }
        
        # Find and parse all Python model files
        models_dir = os.path.join(module_path, 'models')
        if os.path.isdir(models_dir):
            for py_file in self._find_python_files(models_dir):
                models = self._parse_python_models(py_file)
                analysis['models'].extend(models)
        
        # Parse views to get button info
        views_dir = os.path.join(module_path, 'views')
        view_info = {}
        if os.path.isdir(views_dir):
            for xml_file in self._find_xml_files(views_dir):
                view_info.update(self._parse_views(xml_file))
        
        # Merge view info into models
        for model in analysis['models']:
            if model['name'] in view_info:
                model['view_buttons'] = view_info[model['name']].get('buttons', [])
                model['view_fields'] = view_info[model['name']].get('fields', [])
        
        # Parse security rules
        security_file = os.path.join(module_path, 'security', 'ir.model.access.csv')
        if os.path.isfile(security_file):
            analysis['security'] = self._parse_security_csv(security_file)
        
        return analysis

    @api.model
    def _parse_python_models(self, py_file):
        """Parse Python file and extract model definitions"""
        models = []
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    model_info = self._extract_model_info(node, content)
                    if model_info:
                        models.append(model_info)
        
        except Exception as e:
            _logger.warning(f"Failed to parse {py_file}: {e}")
        
        return models

    @api.model
    def _extract_model_info(self, class_node, source_content):
        """Extract model information from AST class node"""
        model_name = None
        inherit = None
        description = None
        fields = []
        methods = []
        constraints = []
        sql_constraints = []
        has_workflow = False
        states = []
        
        for item in class_node.body:
            # Look for _name, _inherit, _description
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == '_name' and isinstance(item.value, ast.Constant):
                            model_name = item.value.value
                        elif target.id == '_inherit':
                            if isinstance(item.value, ast.Constant):
                                inherit = item.value.value
                            elif isinstance(item.value, ast.List):
                                inherit = ', '.join(
                                    el.value for el in item.value.elts 
                                    if isinstance(el, ast.Constant)
                                )
                        elif target.id == '_description' and isinstance(item.value, ast.Constant):
                            description = item.value.value
                        elif target.id == '_sql_constraints' and isinstance(item.value, ast.List):
                            for el in item.value.elts:
                                if isinstance(el, ast.Tuple) and len(el.elts) >= 2:
                                    sql_constraints.append({
                                        'name': el.elts[0].value if isinstance(el.elts[0], ast.Constant) else '',
                                        'message': el.elts[2].value if len(el.elts) > 2 and isinstance(el.elts[2], ast.Constant) else '',
                                    })
            
            # Look for field definitions
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        field_info = self._extract_field_info(target.id, item.value)
                        if field_info:
                            fields.append(field_info)
                            # Check for state field (workflow)
                            if field_info['name'] == 'state' and field_info['type'] == 'Selection':
                                has_workflow = True
                                states = field_info.get('selection', [])
            
            # Look for methods
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_method_info(item)
                if method_info:
                    methods.append(method_info)
                    # Check for constraint decorators
                    for decorator in item.decorator_list:
                        if isinstance(decorator, ast.Call):
                            if hasattr(decorator.func, 'attr') and decorator.func.attr == 'constrains':
                                constraints.append({
                                    'name': item.name,
                                    'fields': [arg.value for arg in decorator.args if isinstance(arg, ast.Constant)]
                                })
        
        if not model_name and not inherit:
            return None
        
        return {
            'name': model_name or inherit,
            'inherit': inherit if model_name else None,
            'description': description or '',
            'fields': fields,
            'field_count': len(fields),
            'methods': methods,
            'method_count': len(methods),
            'constraints': constraints,
            'sql_constraints': sql_constraints,
            'has_constraints': len(constraints) > 0 or len(sql_constraints) > 0,
            'has_workflow': has_workflow,
            'states': states,
        }

    @api.model
    def _extract_field_info(self, field_name, call_node):
        """Extract field information from AST Call node"""
        # Check if it's a fields.X call
        if not isinstance(call_node.func, ast.Attribute):
            return None
        
        if not isinstance(call_node.func.value, ast.Name):
            return None
        
        if call_node.func.value.id != 'fields':
            return None
        
        field_type = call_node.func.attr
        
        field_info = {
            'name': field_name,
            'type': field_type,
            'required': False,
            'readonly': False,
            'compute': None,
            'related': None,
            'default': None,
            'comodel': None,
            'selection': [],
        }
        
        # Parse keyword arguments
        for kw in call_node.keywords:
            if kw.arg == 'required' and isinstance(kw.value, ast.Constant):
                field_info['required'] = kw.value.value
            elif kw.arg == 'readonly' and isinstance(kw.value, ast.Constant):
                field_info['readonly'] = kw.value.value
            elif kw.arg == 'compute' and isinstance(kw.value, ast.Constant):
                field_info['compute'] = kw.value.value
            elif kw.arg == 'related' and isinstance(kw.value, ast.Constant):
                field_info['related'] = kw.value.value
            elif kw.arg == 'comodel_name' and isinstance(kw.value, ast.Constant):
                field_info['comodel'] = kw.value.value
            elif kw.arg == 'selection' and isinstance(kw.value, ast.List):
                for el in kw.value.elts:
                    if isinstance(el, ast.Tuple) and len(el.elts) >= 1:
                        if isinstance(el.elts[0], ast.Constant):
                            field_info['selection'].append(el.elts[0].value)
        
        # Get comodel from first positional arg for Many2one/One2many
        if field_type in ('Many2one', 'One2many', 'Many2many') and call_node.args:
            if isinstance(call_node.args[0], ast.Constant):
                field_info['comodel'] = call_node.args[0].value
        
        return field_info

    @api.model
    def _extract_method_info(self, func_node):
        """Extract method information from AST FunctionDef node"""
        if func_node.name.startswith('_') and not func_node.name.startswith('_compute'):
            is_private = True
        else:
            is_private = False
        
        # Check decorators
        is_api_model = False
        is_api_depends = False
        is_api_onchange = False
        is_api_constrains = False
        depends_fields = []
        onchange_fields = []
        
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                if decorator.attr == 'model':
                    is_api_model = True
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == 'depends':
                    is_api_depends = True
                    depends_fields = [arg.value for arg in decorator.args if isinstance(arg, ast.Constant)]
                elif decorator.func.attr == 'onchange':
                    is_api_onchange = True
                    onchange_fields = [arg.value for arg in decorator.args if isinstance(arg, ast.Constant)]
                elif decorator.func.attr == 'constrains':
                    is_api_constrains = True
        
        # Determine if it's an action method (likely a button)
        is_action = func_node.name.startswith('action_') or func_node.name.startswith('button_')
        
        return {
            'name': func_node.name,
            'is_private': is_private,
            'is_action': is_action,
            'is_compute': is_api_depends or func_node.name.startswith('_compute'),
            'is_onchange': is_api_onchange,
            'is_constraint': is_api_constrains,
            'depends_fields': depends_fields,
            'onchange_fields': onchange_fields,
        }

    @api.model
    def _parse_views(self, xml_file):
        """Parse XML view file and extract button and field info"""
        view_info = {}
        
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find model for each view
            model_pattern = r'<field name="model">([^<]+)</field>'
            arch_pattern = r'<field name="arch"[^>]*>(.*?)</field>'
            
            # Simple parsing - find buttons
            button_pattern = r'<button[^>]*name=["\']([^"\']+)["\'][^>]*>'
            buttons = re.findall(button_pattern, content)
            
            # Find fields used in views
            field_pattern = r'<field[^>]*name=["\']([^"\']+)["\']'
            fields = re.findall(field_pattern, content)
            
            # Try to associate with model
            models = re.findall(model_pattern, content)
            for model in models:
                if model not in view_info:
                    view_info[model] = {'buttons': [], 'fields': []}
                view_info[model]['buttons'].extend(buttons)
                view_info[model]['fields'].extend(fields)
        
        except Exception as e:
            _logger.warning(f"Failed to parse view {xml_file}: {e}")
        
        return view_info

    @api.model
    def _parse_security_csv(self, csv_file):
        """Parse ir.model.access.csv file"""
        rules = []
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if lines:
                # Skip header
                for line in lines[1:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 6:
                        rules.append({
                            'id': parts[0],
                            'model': parts[2] if len(parts) > 2 else '',
                            'group': parts[3] if len(parts) > 3 else '',
                            'perm_read': parts[4] == '1' if len(parts) > 4 else False,
                            'perm_write': parts[5] == '1' if len(parts) > 5 else False,
                            'perm_create': parts[6] == '1' if len(parts) > 6 else False,
                            'perm_unlink': parts[7] == '1' if len(parts) > 7 else False,
                        })
        except Exception as e:
            _logger.warning(f"Failed to parse security file {csv_file}: {e}")
        
        return rules
