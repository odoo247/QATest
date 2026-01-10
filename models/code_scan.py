# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)


class QACodeScan(models.Model):
    _name = 'qa.code.scan'
    _description = 'Code Scan Session'
    _order = 'scan_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    customer_id = fields.Many2one('qa.customer', string='Customer', 
                                   required=True, ondelete='cascade', tracking=True)
    repository_id = fields.Many2one('qa.git.repository', string='Repository',
                                     required=True, ondelete='cascade', tracking=True,
                                     domain="[('customer_id', '=', customer_id)]")
    branch = fields.Char(string='Branch', default='main', required=True)
    commit_hash = fields.Char(string='Commit Hash', readonly=True)
    commit_message = fields.Char(string='Commit Message', readonly=True)
    scan_date = fields.Datetime(string='Scan Date', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scanning', 'Scanning'),
        ('scanned', 'Scanned'),
        ('analyzing', 'Analyzing'),
        ('analyzed', 'Analyzed'),
        ('generating', 'Generating Tests'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], string='Status', default='draft', tracking=True)
    
    # Discovered modules
    module_ids = fields.One2many('qa.scanned.module', 'scan_id', string='Modules')
    module_count = fields.Integer(compute='_compute_counts')
    selected_module_count = fields.Integer(compute='_compute_counts')
    
    # Generated tests
    test_suite_ids = fields.One2many('qa.test.suite', 'code_scan_id', string='Test Suites')
    test_count = fields.Integer(compute='_compute_counts')
    
    # Logs
    scan_log = fields.Text(string='Scan Log', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    
    # Options
    include_crud_tests = fields.Boolean(string='Include CRUD Tests', default=True)
    include_validation_tests = fields.Boolean(string='Include Validation Tests', default=True)
    include_workflow_tests = fields.Boolean(string='Include Workflow Tests', default=True)
    include_security_tests = fields.Boolean(string='Include Security Tests', default=True)
    include_negative_tests = fields.Boolean(string='Include Negative Tests', default=True)
    max_tests_per_model = fields.Integer(string='Max Tests per Model', default=25)

    @api.depends('module_ids', 'module_ids.selected', 'test_suite_ids', 'test_suite_ids.test_case_ids')
    def _compute_counts(self):
        for record in self:
            record.module_count = len(record.module_ids)
            record.selected_module_count = len(record.module_ids.filtered('selected'))
            record.test_count = sum(len(suite.test_case_ids) for suite in record.test_suite_ids)

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            customer = self.env['qa.customer'].browse(vals.get('customer_id'))
            vals['name'] = f"Scan - {customer.code} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return super().create(vals)

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        self.repository_id = False
        return {'domain': {'repository_id': [('customer_id', '=', self.customer_id.id)]}}

    @api.onchange('repository_id')
    def _onchange_repository_id(self):
        if self.repository_id:
            self.branch = self.repository_id.branch or 'main'

    def action_scan_repository(self):
        """Scan repository for Odoo modules"""
        self.ensure_one()
        self.state = 'scanning'
        self.scan_date = fields.Datetime.now()
        self.scan_log = ""
        self.error_message = False
        
        try:
            # Get code scanner service
            scanner = self.env['qa.code.scanner']
            
            self._log("Starting repository scan...")
            self._log(f"Repository: {self.repository_id.name}")
            self._log(f"Branch: {self.branch}")
            
            # Clone/fetch repository
            repo_path, commit_info = scanner.fetch_repository(
                self.repository_id, 
                self.branch
            )
            
            self.commit_hash = commit_info.get('hash', '')[:8]
            self.commit_message = commit_info.get('message', '')[:100]
            self._log(f"Commit: {self.commit_hash} - {self.commit_message}")
            
            # Discover modules
            modules = scanner.discover_modules(repo_path)
            self._log(f"Found {len(modules)} Odoo modules")
            
            # Clear existing modules
            self.module_ids.unlink()
            
            # Create module records
            for mod_data in modules:
                self._log(f"  - {mod_data['name']} ({mod_data['model_count']} models, {mod_data['view_count']} views)")
                self.env['qa.scanned.module'].create({
                    'scan_id': self.id,
                    'technical_name': mod_data['name'],
                    'display_name': mod_data.get('display_name', mod_data['name']),
                    'version': mod_data.get('version', ''),
                    'path': mod_data.get('path', ''),
                    'depends': ','.join(mod_data.get('depends', [])),
                    'model_count': mod_data.get('model_count', 0),
                    'view_count': mod_data.get('view_count', 0),
                    'selected': mod_data.get('model_count', 0) > 0,  # Auto-select if has models
                })
            
            self._log("Scan complete!")
            self.state = 'scanned'
            
        except Exception as e:
            _logger.exception("Code scan failed")
            self.error_message = str(e)
            self.state = 'error'
            self._log(f"ERROR: {str(e)}")
        
        return True

    def action_analyze_modules(self):
        """Analyze selected modules with AI"""
        self.ensure_one()
        
        selected = self.module_ids.filtered('selected')
        if not selected:
            raise UserError(_("Please select at least one module to analyze."))
        
        self.state = 'analyzing'
        
        try:
            scanner = self.env['qa.code.scanner']
            
            for module in selected:
                self._log(f"Analyzing module: {module.technical_name}")
                
                # Get module source code
                repo_path, _ = scanner.fetch_repository(self.repository_id, self.branch)
                module_path = f"{repo_path}/{module.path}"
                
                # Parse module
                analysis = scanner.analyze_module(module_path, module.technical_name)
                
                # Clear existing analyses
                module.analysis_ids.unlink()
                
                # Create analysis records
                for model_data in analysis.get('models', []):
                    self._log(f"  Model: {model_data['name']} - {model_data.get('field_count', 0)} fields, {model_data.get('method_count', 0)} methods")
                    
                    self.env['qa.model.analysis'].create({
                        'module_id': module.id,
                        'model_name': model_data['name'],
                        'model_description': model_data.get('description', ''),
                        'inherit_model': model_data.get('inherit', ''),
                        'field_count': model_data.get('field_count', 0),
                        'method_count': model_data.get('method_count', 0),
                        'has_workflow': model_data.get('has_workflow', False),
                        'has_constraints': model_data.get('has_constraints', False),
                        'analysis_json': json.dumps(model_data, indent=2),
                    })
                
                module.state = 'analyzed'
            
            self._log("Analysis complete!")
            self.state = 'analyzed'
            
        except Exception as e:
            _logger.exception("Module analysis failed")
            self.error_message = str(e)
            self.state = 'error'
            self._log(f"ERROR: {str(e)}")
        
        return True

    def action_generate_tests(self):
        """Generate tests from analyzed modules"""
        self.ensure_one()
        
        analyzed_modules = self.module_ids.filtered(lambda m: m.selected and m.state == 'analyzed')
        if not analyzed_modules:
            raise UserError(_("Please analyze modules first."))
        
        self.state = 'generating'
        total_tests = 0
        
        try:
            ai_generator = self.env['qa.ai.generator']
            
            for module in analyzed_modules:
                self._log(f"Generating tests for: {module.technical_name}")
                
                # Create test suite for module
                suite = self.env['qa.test.suite'].create({
                    'name': f"{self.customer_id.code} - {module.technical_name}",
                    'customer_id': self.customer_id.id,
                    'code_scan_id': self.id,
                    'scanned_module_id': module.id,
                })
                
                # Generate tests for each model
                for analysis in module.analysis_ids:
                    self._log(f"  Generating for model: {analysis.model_name}")
                    
                    # Get test scenarios from AI
                    scenarios = ai_generator.generate_test_scenarios_from_code(
                        analysis,
                        include_crud=self.include_crud_tests,
                        include_validation=self.include_validation_tests,
                        include_workflow=self.include_workflow_tests,
                        include_security=self.include_security_tests,
                        include_negative=self.include_negative_tests,
                        max_tests=self.max_tests_per_model,
                    )
                    
                    # Create test cases
                    for scenario in scenarios:
                        test_case = self.env['qa.test.case'].create({
                            'name': scenario.get('name', 'Test'),
                            'test_id': scenario.get('test_id', ''),
                            'description': scenario.get('description', ''),
                            'category': scenario.get('category', 'functional'),
                            'customer_id': self.customer_id.id,
                            'suite_id': suite.id,
                            'code_scan_id': self.id,
                            'model_analysis_id': analysis.id,
                            'generation_source': 'code_scan',
                            'robot_code': scenario.get('robot_code', ''),
                            'state': 'ready',
                        })
                        
                        # Create test steps
                        for i, step in enumerate(scenario.get('steps', []), 1):
                            self.env['qa.test.step'].create({
                                'test_case_id': test_case.id,
                                'sequence': i,
                                'name': step.get('name', f'Step {i}'),
                                'action': step.get('action', ''),
                                'expected_result': step.get('expected', ''),
                            })
                        
                        total_tests += 1
                    
                    analysis.test_count = len(scenarios)
                
                module.state = 'generated'
                self._log(f"  Created {sum(a.test_count for a in module.analysis_ids)} tests")
            
            self._log(f"Test generation complete! Total: {total_tests} tests")
            self.state = 'done'
            
        except Exception as e:
            _logger.exception("Test generation failed")
            self.error_message = str(e)
            self.state = 'error'
            self._log(f"ERROR: {str(e)}")
        
        return True

    def action_scan_and_generate(self):
        """Full workflow: scan, analyze, generate"""
        self.action_scan_repository()
        if self.state == 'scanned':
            self.action_analyze_modules()
        if self.state == 'analyzed':
            self.action_generate_tests()
        return True

    def action_view_tests(self):
        """View generated test cases"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tests - {self.name}',
            'res_model': 'qa.test.case',
            'view_mode': 'list,form',
            'domain': [('code_scan_id', '=', self.id)],
            'context': {'default_customer_id': self.customer_id.id},
        }

    def action_view_suites(self):
        """View generated test suites"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Suites - {self.name}',
            'res_model': 'qa.test.suite',
            'view_mode': 'list,form',
            'domain': [('code_scan_id', '=', self.id)],
        }

    def action_reset_draft(self):
        """Reset to draft state"""
        self.ensure_one()
        self.state = 'draft'
        self.error_message = False

    def _log(self, message):
        """Append to scan log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"
        self.scan_log = (self.scan_log or '') + log_line

