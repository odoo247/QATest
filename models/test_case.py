# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class QATestCase(models.Model):
    _name = 'qa.test.case'
    _description = 'Test Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Test Case Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    
    # Classification
    test_id = fields.Char(string='Test ID', readonly=True, copy=False)
    description = fields.Text(string='Description')
    category = fields.Selection([
        ('functional', 'Functional'),
        ('integration', 'Integration'),
        ('regression', 'Regression'),
        ('smoke', 'Smoke'),
        ('e2e', 'End-to-End'),
    ], string='Category', default='functional')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Critical'),
    ], string='Priority', default='1')
    tags = fields.Char(string='Tags', help='Comma-separated tags for Robot Framework')
    
    # Relations
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   ondelete='cascade')
    requirement_id = fields.Many2one('qa.requirement', string='Requirement',
                                      ondelete='set null',
                                      help='Acceptance test for this requirement')
    regression_suite_id = fields.Many2one('qa.regression.suite', string='Regression Suite',
                                           ondelete='set null')
    template_id = fields.Many2one('qa.regression.template', string='Template',
                                   ondelete='set null')
    spec_id = fields.Many2one('qa.test.spec', string='Source Specification', 
                              ondelete='cascade')
    suite_id = fields.Many2one('qa.test.suite', string='Test Suite',
                               ondelete='set null',
                               help='Test suite this test belongs to')
    
    # Code-First Generation
    code_scan_id = fields.Many2one('qa.code.scan', string='Code Scan',
                                    ondelete='set null')
    model_analysis_id = fields.Many2one('qa.model.analysis', string='Model Analysis',
                                         ondelete='set null')
    generation_source = fields.Selection([
        ('manual', 'Manual'),
        ('specification', 'From Specification'),
        ('requirement', 'From Requirement'),
        ('code_scan', 'From Code Scan'),
        ('template', 'From Template'),
    ], string='Generation Source', default='manual')
    
    step_ids = fields.One2many('qa.test.step', 'test_case_id', string='Test Steps')
    result_ids = fields.One2many('qa.test.result', 'test_case_id', string='Results')
    
    # Test Type
    test_type = fields.Selection([
        ('acceptance', 'Acceptance Test'),
        ('regression', 'Regression Test'),
        ('integration', 'Integration Test'),
        ('manual', 'Manual Test'),
    ], string='Test Type', default='acceptance')
    
    # Robot Framework Code
    robot_code = fields.Text(string='Robot Framework Code', required=True)
    robot_code_preview = fields.Html(string='Code Preview', compute='_compute_code_preview')
    
    # Keywords (extracted from robot code)
    setup_keyword = fields.Text(string='Test Setup')
    teardown_keyword = fields.Text(string='Test Teardown')
    
    # Documentation
    documentation = fields.Text(string='Test Documentation')
    preconditions = fields.Text(string='Preconditions')
    expected_result = fields.Text(string='Expected Result')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('running', 'Running'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ], string='Status', default='draft', tracking=True)
    
    # Last execution info
    last_run_date = fields.Datetime(string='Last Run Date', readonly=True)
    last_run_duration = fields.Float(string='Last Duration (s)', readonly=True)
    last_run_result_id = fields.Many2one('qa.test.result', string='Last Result',
                                         compute='_compute_last_run')
    last_result = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], string='Last Result Status', compute='_compute_last_run', store=True)
    last_error_message = fields.Text(string='Last Error', readonly=True)
    last_screenshot = fields.Binary(string='Last Screenshot', readonly=True)
    last_screenshot_name = fields.Char(string='Screenshot Name')
    
    # Statistics
    total_runs = fields.Integer(string='Total Runs', compute='_compute_statistics')
    pass_count = fields.Integer(string='Pass Count', compute='_compute_statistics')
    fail_count = fields.Integer(string='Fail Count', compute='_compute_statistics')
    pass_rate = fields.Float(string='Pass Rate (%)', compute='_compute_statistics')
    avg_duration = fields.Float(string='Avg Duration (s)', compute='_compute_statistics')
    
    # AI-related
    ai_generated = fields.Boolean(string='AI Generated', default=True)
    ai_model = fields.Char(string='AI Model Used')
    generation_date = fields.Datetime(string='Generation Date')
    
    # Manual modifications
    manually_modified = fields.Boolean(string='Manually Modified', default=False)
    modification_notes = fields.Text(string='Modification Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('test_id'):
                vals['test_id'] = self.env['ir.sequence'].next_by_code('qa.test.case') or 'TC0001'
        return super().create(vals_list)

    @api.depends('robot_code')
    def _compute_code_preview(self):
        for record in self:
            if record.robot_code:
                # Escape HTML and wrap in pre tag
                import html
                escaped = html.escape(record.robot_code)
                record.robot_code_preview = f'<pre style="background:#f5f5f5;padding:10px;border-radius:4px;overflow-x:auto;"><code>{escaped}</code></pre>'
            else:
                record.robot_code_preview = '<p>No code generated yet.</p>'

    @api.depends('result_ids', 'result_ids.status')
    def _compute_last_run(self):
        for record in self:
            last_result = record.result_ids.sorted('execution_date', reverse=True)[:1]
            record.last_run_result_id = last_result.id if last_result else False
            if last_result and last_result.status in ('passed', 'failed'):
                record.last_result = last_result.status
            else:
                record.last_result = False

    @api.depends('result_ids', 'result_ids.status')
    def _compute_statistics(self):
        for record in self:
            results = record.result_ids
            record.total_runs = len(results)
            record.pass_count = len(results.filtered(lambda r: r.status == 'passed'))
            record.fail_count = len(results.filtered(lambda r: r.status == 'failed'))
            record.pass_rate = (record.pass_count / record.total_runs * 100) if record.total_runs else 0
            durations = results.mapped('duration')
            record.avg_duration = sum(durations) / len(durations) if durations else 0

    def action_run_test(self):
        """Run this single test case"""
        self.ensure_one()
        return {
            'name': 'Run Test',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.run.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_test_case_ids': [(6, 0, [self.id])],
            }
        }

    def action_view_results(self):
        """View execution results for this test"""
        self.ensure_one()
        return {
            'name': 'Test Results',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.result',
            'view_mode': 'list,form',
            'domain': [('test_case_id', '=', self.id)],
        }

    def action_regenerate(self):
        """Regenerate this test case from its specification"""
        self.ensure_one()
        if not self.spec_id:
            raise UserError('No source specification found.')
        
        # Mark as draft and regenerate
        self.state = 'draft'
        self.spec_id._generate_tests()
        
        return True

    def action_edit_code(self):
        """Open code editor wizard"""
        self.ensure_one()
        return {
            'name': 'Edit Test Code',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.case',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_mark_ready(self):
        """Mark test as ready for execution"""
        self.write({'state': 'ready'})

    def action_export_robot(self):
        """Export this test case as a .robot file"""
        self.ensure_one()
        
        from ..services.robot_generator import RobotGenerator
        config = self.env['qa.test.ai.config'].get_active_config()
        generator = RobotGenerator(config)
        
        file_content = generator.generate_single_test_file(self)
        file_name = f"{self.test_id}_{self.name.replace(' ', '_')}.robot"
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': base64.b64encode(file_content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/plain',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_view_screenshot(self):
        """View last screenshot in popup"""
        self.ensure_one()
        if not self.last_screenshot:
            raise UserError('No screenshot available.')
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Screenshot',
            'res_model': 'qa.test.case',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('qa_test_generator.view_test_case_screenshot_popup').id,
            'target': 'new',
        }

    def write(self, vals):
        if 'robot_code' in vals and not self.env.context.get('from_ai'):
            vals['manually_modified'] = True
        return super().write(vals)

    def _execute(self, run_id):
        """Execute this test case (called by test run)"""
        self.ensure_one()
        self.state = 'running'
        
        try:
            from ..services.test_executor import TestExecutor
            
            # Get config
            config = self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
            
            # Get run info for server/target_url
            run = self.env['qa.test.run'].browse(run_id)
            server = run.server_id if run else None
            target_url = run.target_url if run else None
            
            executor = TestExecutor(config, server=server, target_url=target_url)
            
            result = executor.execute_test(self)
            
            # Create result record
            result_record = self.env['qa.test.result'].create({
                'test_case_id': self.id,
                'run_id': run_id,
                'status': result.get('status', 'error'),
                'duration': result.get('duration', 0),
                'message': result.get('message', ''),
                'log': result.get('log', ''),
                'screenshot': result.get('screenshot'),
            })
            
            # Update test case status
            self.write({
                'state': result.get('status', 'error'),
                'last_run_date': fields.Datetime.now(),
                'last_run_duration': result.get('duration', 0),
                'last_error_message': result.get('message') if result.get('status') != 'passed' else False,
                'last_screenshot': result.get('screenshot'),
            })
            
            return result_record
            
        except Exception as e:
            _logger.error(f"Test execution failed: {str(e)}")
            self.write({
                'state': 'error',
                'last_error_message': str(e),
            })
            raise
