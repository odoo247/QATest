# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class QAFixTestsWizard(models.TransientModel):
    _name = 'qa.fix.tests.wizard'
    _description = 'Fix Failed Tests Wizard'

    # Source selection
    source_type = fields.Selection([
        ('run', 'From Test Run'),
        ('selected', 'Selected Test Cases'),
    ], string='Source', default='run', required=True)
    
    run_id = fields.Many2one('qa.test.run', string='Test Run',
                              domain="[('state', 'in', ['failed', 'error'])]")
    test_case_ids = fields.Many2many('qa.test.case', string='Test Cases',
                                      domain="[('state', 'in', ['failed', 'error'])]")
    
    # Configuration
    config_id = fields.Many2one('qa.test.ai.config', string='AI Configuration',
                                 default=lambda self: self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1))
    
    # Analysis results
    line_ids = fields.One2many('qa.fix.tests.wizard.line', 'wizard_id', string='Test Fixes')
    
    # Options
    auto_apply = fields.Boolean(string='Auto-apply All Fixes', default=False,
                                 help='Automatically apply all suggested fixes without review')
    include_context = fields.Boolean(string='Include Error Context', default=True,
                                      help='Send error messages to AI for better analysis')
    
    # Progress
    state = fields.Selection([
        ('draft', 'Select Tests'),
        ('analyzing', 'Analyzing...'),
        ('review', 'Review Fixes'),
        ('done', 'Complete'),
    ], string='State', default='draft')
    
    analyzed_count = fields.Integer(string='Analyzed', default=0)
    total_count = fields.Integer(string='Total', default=0)
    fixed_count = fields.Integer(string='Fixed', compute='_compute_fixed_count')

    @api.depends('line_ids.applied')
    def _compute_fixed_count(self):
        for record in self:
            record.fixed_count = len(record.line_ids.filtered('applied'))

    @api.onchange('source_type', 'run_id')
    def _onchange_source(self):
        if self.source_type == 'run' and self.run_id:
            # Get failed results from run
            failed_results = self.run_id.result_ids.filtered(
                lambda r: r.status in ('failed', 'error')
            )
            _logger.info(f"Found {len(failed_results)} failed results in run {self.run_id.id}")
            
            # Get test cases from linked results
            linked_test_cases = failed_results.filtered('test_case_id').mapped('test_case_id')
            _logger.info(f"Found {len(linked_test_cases)} linked test cases")
            
            # Also include test cases from the run itself that are in failed state
            run_failed_cases = self.run_id.test_case_ids.filtered(
                lambda tc: tc.state in ('failed', 'error')
            )
            _logger.info(f"Found {len(run_failed_cases)} failed test cases in run")
            
            # Combine both
            all_failed = linked_test_cases | run_failed_cases
            self.test_case_ids = all_failed
            
            _logger.info(f"Total test cases for fixing: {len(self.test_case_ids)}")

    def action_analyze(self):
        """Analyze failed tests and generate fixes using AI"""
        self.ensure_one()
        
        if not self.config_id:
            raise UserError('Please configure AI settings first.')
        
        # Refresh test_case_ids from source
        if self.source_type == 'run' and self.run_id:
            self._onchange_source()
        
        if not self.test_case_ids:
            raise UserError('No failed test cases found. Make sure the test results are linked to test cases, or select test cases manually.')
        
        self.state = 'analyzing'
        self.total_count = len(self.test_case_ids)
        self.analyzed_count = 0
        
        # Clear existing lines
        self.line_ids.unlink()
        
        lines_data = []
        
        for test_case in self.test_case_ids:
            try:
                _logger.info(f"Analyzing test case: {test_case.name} (ID: {test_case.id})")
                
                # Get last error message
                error_message = test_case.last_error_message or ''
                
                # If we have a run, get the specific result
                if self.run_id:
                    result = self.run_id.result_ids.filtered(
                        lambda r: r.test_case_id.id == test_case.id
                    )[:1]
                    if result:
                        error_message = result.message or error_message
                
                robot_code = test_case.robot_code or ''
                
                if not robot_code:
                    _logger.warning(f"Test case {test_case.name} has no robot_code")
                    lines_data.append({
                        'wizard_id': self.id,
                        'test_case_id': test_case.id,
                        'original_code': '',
                        'error_message': error_message[:2000] if error_message else 'No error message',
                        'analysis': 'Test case has no Robot Framework code. Generate code first or write it manually.',
                        'suggested_fix': '',
                        'fix_type': 'manual_review',
                        'confidence': 'low',
                    })
                    self.analyzed_count += 1
                    continue
                
                # Analyze with AI
                analysis = self._analyze_test_with_ai(test_case, error_message)
                
                lines_data.append({
                    'wizard_id': self.id,
                    'test_case_id': test_case.id,
                    'original_code': robot_code,
                    'error_message': error_message[:2000] if error_message else '',
                    'analysis': analysis.get('analysis', ''),
                    'suggested_fix': analysis.get('fixed_code', ''),
                    'fix_type': analysis.get('fix_type', 'code_fix'),
                    'confidence': analysis.get('confidence', 'medium'),
                })
                
                self.analyzed_count += 1
                _logger.info(f"Analysis complete for {test_case.name}: {analysis.get('fix_type')}")
                
            except Exception as e:
                _logger.error(f"Error analyzing test {test_case.name}: {e}")
                lines_data.append({
                    'wizard_id': self.id,
                    'test_case_id': test_case.id,
                    'original_code': test_case.robot_code or '',
                    'error_message': str(e),
                    'analysis': f'Analysis failed: {str(e)}',
                    'suggested_fix': '',
                    'fix_type': 'manual_review',
                    'confidence': 'low',
                })
        
        # Create all lines
        if lines_data:
            self.env['qa.fix.tests.wizard.line'].create(lines_data)
            _logger.info(f"Created {len(lines_data)} wizard lines")
        
        self.state = 'review'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _analyze_test_with_ai(self, test_case, error_message):
        """Use AI to analyze test failure and suggest fix"""
        
        prompt = f"""Analyze this failed Robot Framework test and provide a fix.

## Test Case: {test_case.name}
## Test ID: {test_case.test_id}

## Original Robot Code:
```robot
{test_case.robot_code}
```

## Error Message:
```
{error_message}
```

## Your Task:
1. Analyze why the test failed
2. Provide the corrected Robot Framework code
3. Explain what was wrong and how you fixed it

## Common Issues to Check:
- `Should Not Be Empty` doesn't work on integers - use `Should Be True    ${{var}} > 0` instead
- Field names may differ between Odoo versions
- Validation tests should use `Run Keyword And Expect Error` to expect failures
- Empty records can't be posted - need to add required data first
- Some fields are computed/readonly and can't be set directly

## Response Format (JSON):
{{
    "analysis": "Brief explanation of what went wrong",
    "fix_type": "code_fix|skip_test|validation_test|manual_review",
    "confidence": "high|medium|low",
    "fixed_code": "The complete corrected robot code for this test case"
}}

Respond ONLY with the JSON object, no other text.
"""

        try:
            from ..services.ai_generator import AIGenerator
            generator = AIGenerator(self.config_id)
            
            response = generator._call_api(prompt)
            
            # Parse JSON response
            # Try to extract JSON from response
            response_text = response.strip()
            
            # Handle markdown code blocks
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            result = json.loads(response_text)
            
            return {
                'analysis': result.get('analysis', ''),
                'fix_type': result.get('fix_type', 'code_fix'),
                'confidence': result.get('confidence', 'medium'),
                'fixed_code': result.get('fixed_code', ''),
            }
            
        except json.JSONDecodeError as e:
            _logger.warning(f"Failed to parse AI response as JSON: {e}")
            # Return the raw response as analysis
            return {
                'analysis': response_text if 'response_text' in dir() else str(e),
                'fix_type': 'manual_review',
                'confidence': 'low',
                'fixed_code': '',
            }
        except Exception as e:
            _logger.error(f"AI analysis failed: {e}")
            raise

    def action_apply_all(self):
        """Apply all suggested fixes"""
        self.ensure_one()
        
        _logger.info(f"action_apply_all: Total lines: {len(self.line_ids)}")
        
        applicable_lines = self.line_ids.filtered(lambda l: l.suggested_fix and not l.applied)
        _logger.info(f"action_apply_all: Applicable lines: {len(applicable_lines)}")
        
        if not applicable_lines:
            # Check why no lines are applicable
            all_lines = self.line_ids
            already_applied = all_lines.filtered('applied')
            no_fix = all_lines.filtered(lambda l: not l.suggested_fix)
            
            msg_parts = []
            if not all_lines:
                msg_parts.append("No test analyses found. Click 'Analyze with AI' first.")
            else:
                if already_applied:
                    msg_parts.append(f"{len(already_applied)} already applied")
                if no_fix:
                    msg_parts.append(f"{len(no_fix)} have no suggested fix")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Fixes to Apply',
                    'message': ' | '.join(msg_parts) if msg_parts else 'No fixes available.',
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        applied_count = 0
        errors = []
        
        for line in applicable_lines:
            try:
                line.action_apply_fix()
                applied_count += 1
            except Exception as e:
                errors.append(f"{line.test_name}: {str(e)}")
                _logger.error(f"Failed to apply fix for {line.test_name}: {e}")
        
        self.state = 'done'
        
        message = f'{applied_count} test cases updated.'
        if errors:
            message += f' {len(errors)} failed: ' + ', '.join(errors[:3])
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fixes Applied',
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }

    def action_apply_selected(self):
        """Apply only selected/reviewed fixes"""
        self.ensure_one()
        
        for line in self.line_ids.filtered(lambda l: l.selected and l.suggested_fix and not l.applied):
            line.action_apply_fix()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_rerun_tests(self):
        """Create new test run with fixed tests"""
        self.ensure_one()
        
        fixed_tests = self.line_ids.filtered('applied').mapped('test_case_id')
        
        if not fixed_tests:
            raise UserError('No fixes have been applied yet.')
        
        # Create new run
        run = self.env['qa.test.run'].create({
            'name': f"Rerun - {self.run_id.name}" if self.run_id else "Rerun Fixed Tests",
            'customer_id': self.run_id.customer_id.id if self.run_id else False,
            'server_id': self.run_id.server_id.id if self.run_id else False,
            'suite_id': self.run_id.suite_id.id if self.run_id else False,
            'test_case_ids': [(6, 0, fixed_tests.ids)],
            'config_id': self.config_id.id,
            'triggered_by': 'manual',
        })
        
        return {
            'name': 'Test Run',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }


class QAFixTestsWizardLine(models.TransientModel):
    _name = 'qa.fix.tests.wizard.line'
    _description = 'Fix Tests Wizard Line'

    wizard_id = fields.Many2one('qa.fix.tests.wizard', string='Wizard', ondelete='cascade')
    test_case_id = fields.Many2one('qa.test.case', string='Test Case', required=True)
    test_name = fields.Char(related='test_case_id.name', string='Test Name')
    test_id = fields.Char(related='test_case_id.test_id', string='Test ID')
    
    # Original data
    original_code = fields.Text(string='Original Code')
    error_message = fields.Text(string='Error Message')
    
    # AI Analysis
    analysis = fields.Text(string='Analysis')
    suggested_fix = fields.Text(string='Suggested Fix')
    fix_type = fields.Selection([
        ('code_fix', 'Code Fix'),
        ('skip_test', 'Skip Test'),
        ('validation_test', 'Convert to Validation Test'),
        ('manual_review', 'Needs Manual Review'),
    ], string='Fix Type', default='code_fix')
    confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Confidence', default='medium')
    
    # User actions
    selected = fields.Boolean(string='Select', default=True)
    applied = fields.Boolean(string='Applied', default=False)
    edited_fix = fields.Text(string='Edited Fix',
                              help='Edit the suggested fix before applying')

    def action_apply_fix(self):
        """Apply the fix to the test case"""
        self.ensure_one()
        
        fix_code = self.edited_fix or self.suggested_fix
        
        if not fix_code:
            _logger.warning(f"No fix code for {self.test_name}")
            return False
        
        if not self.test_case_id:
            raise UserError('No test case linked to this fix.')
        
        _logger.info(f"Applying fix to test case {self.test_case_id.name}, fix_type={self.fix_type}")
        
        if self.fix_type == 'skip_test':
            self.test_case_id.write({
                'state': 'skipped',
                'modification_notes': f"Skipped by AI Fix Wizard: {self.analysis[:500] if self.analysis else 'No analysis'}",
            })
        else:
            self.test_case_id.write({
                'robot_code': fix_code,
                'state': 'ready',
                'manually_modified': True,
                'modification_notes': f"AI Fix Applied: {self.analysis[:500] if self.analysis else 'No analysis'}",
            })
        
        self.applied = True
        _logger.info(f"Fix applied successfully to {self.test_case_id.name}")
        
        return True

    def action_view_diff(self):
        """View diff between original and suggested fix"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qa.fix.tests.wizard.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_diff': True},
        }

    def action_edit_fix(self):
        """Open editor for the fix"""
        self.ensure_one()
        
        if not self.edited_fix:
            self.edited_fix = self.suggested_fix
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qa.fix.tests.wizard.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_skip_test(self):
        """Mark test to be skipped"""
        self.ensure_one()
        self.fix_type = 'skip_test'
        self.selected = True
        return True

    def action_reject_fix(self):
        """Reject the suggested fix"""
        self.ensure_one()
        self.selected = False
        return True
