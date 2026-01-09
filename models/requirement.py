# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QARequirement(models.Model):
    """Customer Requirement - the source of acceptance tests"""
    _name = 'qa.requirement'
    _description = 'Customer Requirement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'customer_id, sequence, id'

    name = fields.Char(string='Requirement Title', required=True, tracking=True)
    code = fields.Char(string='Requirement ID', required=True, 
                       help='Unique identifier (e.g., REQ-001)')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Customer
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   required=True, ondelete='cascade')
    
    # Requirement Details
    description = fields.Html(string='Description',
                              help='What the customer requested')
    acceptance_criteria = fields.Html(string='Acceptance Criteria',
                                      help='How we know it works correctly')
    business_value = fields.Text(string='Business Value',
                                 help='Why this is important to customer')
    
    # Classification
    category = fields.Selection([
        ('feature', 'New Feature'),
        ('enhancement', 'Enhancement'),
        ('bugfix', 'Bug Fix'),
        ('integration', 'Integration'),
        ('report', 'Report/Document'),
        ('workflow', 'Workflow Change'),
        ('config', 'Configuration'),
    ], string='Category', default='feature', required=True)
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Critical'),
    ], string='Priority', default='1')
    
    # Implementation
    affected_modules = fields.Char(string='Affected Modules',
                                   help='Comma-separated module names')
    affected_models = fields.Char(string='Affected Models',
                                  help='Comma-separated model names')
    git_branch = fields.Char(string='Git Branch')
    git_commits = fields.Text(string='Related Commits')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('implementing', 'In Development'),
        ('testing', 'Testing'),
        ('deployed', 'Deployed'),
        ('verified', 'Verified'),
    ], string='Status', default='draft', tracking=True)
    
    # Relations
    test_ids = fields.One2many('qa.test.case', 'requirement_id', 
                                string='Acceptance Tests')
    test_count = fields.Integer(compute='_compute_counts')
    
    # Verification
    verified_date = fields.Datetime(string='Verified Date')
    verified_by_id = fields.Many2one('res.users', string='Verified By')
    last_test_result = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('not_run', 'Not Run'),
    ], compute='_compute_last_result')

    _sql_constraints = [
        ('code_customer_unique', 'UNIQUE(code, customer_id)', 
         'Requirement code must be unique per customer'),
    ]

    @api.depends('test_ids')
    def _compute_counts(self):
        for record in self:
            record.test_count = len(record.test_ids)

    @api.depends('test_ids.last_result')
    def _compute_last_result(self):
        for record in self:
            if not record.test_ids:
                record.last_test_result = 'not_run'
            elif all(t.last_result == 'passed' for t in record.test_ids if t.last_result):
                record.last_test_result = 'passed'
            elif any(t.last_result == 'failed' for t in record.test_ids):
                record.last_test_result = 'failed'
            else:
                record.last_test_result = 'not_run'

    def action_generate_tests(self):
        """Generate acceptance tests from requirement using AI"""
        self.ensure_one()
        
        # Get AI config
        config = self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError("Please configure AI settings first")
        
        from ..services.ai_generator import AITestGenerator
        generator = AITestGenerator(config)
        
        # Build prompt from requirement
        prompt = f"""
Generate acceptance test cases for this customer requirement:

REQUIREMENT: {self.name}
ID: {self.code}
CATEGORY: {self.category}

DESCRIPTION:
{self.description or 'N/A'}

ACCEPTANCE CRITERIA:
{self.acceptance_criteria or 'N/A'}

AFFECTED MODULES: {self.affected_modules or 'N/A'}
AFFECTED MODELS: {self.affected_models or 'N/A'}

Generate Robot Framework test cases that verify this requirement is met.
Include:
1. Positive tests (happy path)
2. Edge cases
3. Negative tests (invalid inputs, error handling)

For each test, provide:
- Test name
- Description
- Preconditions
- Test steps
- Expected results
"""
        
        # Generate tests
        self.state = 'testing'
        result = generator.generate_tests(prompt, context={
            'customer': self.customer_id.name,
            'odoo_version': self.customer_id.odoo_version,
        })
        
        # Create test cases from result
        for test_data in result.get('test_cases', []):
            self.env['qa.test.case'].create({
                'name': test_data.get('name'),
                'description': test_data.get('description'),
                'requirement_id': self.id,
                'customer_id': self.customer_id.id,
                'test_type': 'acceptance',
                'preconditions': test_data.get('preconditions'),
                'expected_result': test_data.get('expected_result'),
                'robot_code': test_data.get('robot_code'),
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tests Generated',
                'message': f'Created {len(result.get("test_cases", []))} acceptance tests',
                'type': 'success',
            }
        }

    def action_verify(self):
        """Mark requirement as verified"""
        self.ensure_one()
        if self.last_test_result != 'passed':
            raise UserError("Cannot verify - tests have not passed")
        
        self.write({
            'state': 'verified',
            'verified_date': fields.Datetime.now(),
            'verified_by_id': self.env.user.id,
        })
