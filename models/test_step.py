# -*- coding: utf-8 -*-

from odoo import models, fields, api


class QATestStep(models.Model):
    _name = 'qa.test.step'
    _description = 'Test Step'
    _order = 'sequence, id'

    name = fields.Char(string='Step Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Parent test case
    test_case_id = fields.Many2one('qa.test.case', string='Test Case', 
                                   required=True, ondelete='cascade')
    
    # Step details
    action = fields.Selection([
        ('navigate', 'Navigate'),
        ('click', 'Click'),
        ('input', 'Input Text'),
        ('select', 'Select Option'),
        ('wait', 'Wait'),
        ('verify', 'Verify'),
        ('screenshot', 'Take Screenshot'),
        ('custom', 'Custom Keyword'),
    ], string='Action Type', required=True, default='click')
    
    # Target element
    locator_type = fields.Selection([
        ('xpath', 'XPath'),
        ('id', 'ID'),
        ('name', 'Name'),
        ('css', 'CSS Selector'),
        ('text', 'Text'),
        ('class', 'Class Name'),
    ], string='Locator Type', default='xpath')
    locator_value = fields.Char(string='Locator Value')
    
    # Action parameters
    input_value = fields.Char(string='Input Value',
                              help='Value to input or expected value to verify')
    wait_time = fields.Float(string='Wait Time (s)', default=0)
    
    # For custom keywords
    keyword_name = fields.Char(string='Keyword Name')
    keyword_args = fields.Char(string='Keyword Arguments')
    
    # Robot Framework line
    robot_line = fields.Char(string='Robot Framework Line', compute='_compute_robot_line')
    
    # Description
    description = fields.Text(string='Description')
    
    # Status (after execution)
    last_status = fields.Selection([
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ], string='Last Status', default='pending')
    last_error = fields.Text(string='Last Error')
    last_screenshot = fields.Binary(string='Step Screenshot')

    @api.depends('action', 'locator_type', 'locator_value', 'input_value', 
                 'keyword_name', 'keyword_args', 'wait_time')
    def _compute_robot_line(self):
        for step in self:
            line = ''
            if step.action == 'navigate':
                line = f"    Go To    {step.input_value or '${BASE_URL}'}"
            elif step.action == 'click':
                locator = step._get_locator()
                line = f"    Click Element    {locator}"
            elif step.action == 'input':
                locator = step._get_locator()
                line = f"    Input Text    {locator}    {step.input_value or ''}"
            elif step.action == 'select':
                locator = step._get_locator()
                line = f"    Select From List By Label    {locator}    {step.input_value or ''}"
            elif step.action == 'wait':
                if step.locator_value:
                    locator = step._get_locator()
                    line = f"    Wait Until Element Is Visible    {locator}    timeout={step.wait_time}s"
                else:
                    line = f"    Sleep    {step.wait_time}s"
            elif step.action == 'verify':
                locator = step._get_locator()
                if step.input_value:
                    line = f"    Element Should Contain    {locator}    {step.input_value}"
                else:
                    line = f"    Element Should Be Visible    {locator}"
            elif step.action == 'screenshot':
                line = f"    Capture Page Screenshot    {step.input_value or 'step_screenshot.png'}"
            elif step.action == 'custom':
                args = step.keyword_args or ''
                line = f"    {step.keyword_name}    {args}"
            
            step.robot_line = line

    def _get_locator(self):
        """Generate Robot Framework locator string"""
        if not self.locator_value:
            return ''
        
        if self.locator_type == 'xpath':
            return self.locator_value
        elif self.locator_type == 'id':
            return f"id={self.locator_value}"
        elif self.locator_type == 'name':
            return f"name={self.locator_value}"
        elif self.locator_type == 'css':
            return f"css={self.locator_value}"
        elif self.locator_type == 'text':
            return f"//\*[contains(text(),'{self.locator_value}')]"
        elif self.locator_type == 'class':
            return f"class={self.locator_value}"
        return self.locator_value
