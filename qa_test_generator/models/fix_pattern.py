# -*- coding: utf-8 -*-

import logging
import re
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class QAFixPattern(models.Model):
    """Store VERIFIED fix patterns - only patterns that actually worked"""
    _name = 'qa.fix.pattern'
    _description = 'QA Fix Pattern'
    _order = 'success_count desc, id desc'

    name = fields.Char(string='Pattern Name', required=True)
    active = fields.Boolean(default=True)
    
    # Error matching - the key identifier
    error_pattern = fields.Char(string='Error Pattern', required=True,
                                help='Key error text to match (case-insensitive)')
    error_regex = fields.Char(string='Error Regex', 
                              help='Optional regex for more precise matching')
    
    # Context
    model_name = fields.Char(string='Model', help='Odoo model this applies to')
    odoo_version_min = fields.Char(string='Min Odoo Version', help='e.g., 17.0')
    odoo_version_max = fields.Char(string='Max Odoo Version', help='e.g., 19.0')
    
    # The fix - human-readable
    problem = fields.Text(string='Problem', required=True)
    solution = fields.Text(string='Solution', required=True)
    
    # Code examples - for AI prompt
    wrong_code = fields.Text(string='Wrong Code')
    correct_code = fields.Text(string='Correct Code')
    
    # Verification tracking
    verified = fields.Boolean(string='Verified', default=False,
                              help='True = This fix has been tested and works')
    verified_by = fields.Many2one('res.users', string='Verified By')
    verified_date = fields.Datetime(string='Verified Date')
    
    # Usage stats
    times_suggested = fields.Integer(string='Times Suggested', default=0)
    success_count = fields.Integer(string='Success Count', default=0)
    success_rate = fields.Float(string='Success Rate %', compute='_compute_success_rate')
    
    # Source tracking
    source = fields.Selection([
        ('system', 'System Default'),
        ('learned', 'Learned from Fix'),
        ('manual', 'Manually Added'),
    ], string='Source', default='manual')
    source_test_case_id = fields.Many2one('qa.test.case', string='Source Test Case')
    source_error = fields.Text(string='Original Error')

    _sql_constraints = [
        ('error_pattern_model_unique', 'unique(error_pattern, model_name)', 
         'This error pattern already exists for this model!')
    ]

    @api.depends('times_suggested', 'success_count')
    def _compute_success_rate(self):
        for rec in self:
            if rec.times_suggested > 0:
                rec.success_rate = (rec.success_count / rec.times_suggested) * 100
            else:
                rec.success_rate = 0

    @api.model
    def find_matching_patterns(self, error_message, model_name=None, odoo_version=None):
        """Find verified patterns matching this error"""
        if not error_message:
            return self.browse()
        
        error_lower = error_message.lower()
        
        # Only get verified, active patterns
        patterns = self.search([
            ('active', '=', True),
            ('verified', '=', True),
        ], order='success_count desc')
        
        matching = self.browse()
        for p in patterns:
            # Check error pattern match
            if p.error_pattern.lower() not in error_lower:
                continue
            
            # Check model match
            if p.model_name and model_name and p.model_name != model_name:
                continue
            
            # Check version match
            if odoo_version and p.odoo_version_min:
                if odoo_version < p.odoo_version_min:
                    continue
            if odoo_version and p.odoo_version_max:
                if odoo_version > p.odoo_version_max:
                    continue
            
            matching |= p
        
        # Mark as suggested
        matching.write({'times_suggested': fields.Integer()})  # Will increment in SQL
        if matching:
            self.env.cr.execute(
                "UPDATE qa_fix_pattern SET times_suggested = times_suggested + 1 WHERE id IN %s",
                (tuple(matching.ids),)
            )
        
        return matching

    def format_for_prompt(self):
        """Format this pattern for AI prompt"""
        result = f"### {self.name}\n"
        result += f"**Error:** `{self.error_pattern}`\n"
        result += f"**Problem:** {self.problem}\n"
        result += f"**Solution:** {self.solution}\n"
        
        if self.wrong_code:
            result += f"**WRONG:**\n```robot\n{self.wrong_code}\n```\n"
        if self.correct_code:
            result += f"**CORRECT:**\n```robot\n{self.correct_code}\n```\n"
        
        return result

    @api.model
    def get_patterns_for_prompt(self, error_message, model_name=None, limit=5):
        """Get formatted patterns for AI prompt"""
        patterns = self.find_matching_patterns(error_message, model_name)[:limit]
        
        if not patterns:
            return ""
        
        result = "\n## VERIFIED FIX PATTERNS (these fixes have worked before):\n\n"
        for p in patterns:
            result += p.format_for_prompt() + "\n"
        
        return result

    def action_mark_success(self):
        """Mark that this pattern led to a successful fix"""
        self.env.cr.execute(
            "UPDATE qa_fix_pattern SET success_count = success_count + 1 WHERE id IN %s",
            (tuple(self.ids),)
        )

    @api.model
    def create_verified_pattern(self, error_message, problem, solution, 
                                 wrong_code=None, correct_code=None,
                                 model_name=None, test_case=None):
        """
        Create a new VERIFIED pattern from a successful fix.
        Called only after human approval.
        """
        # Extract key error pattern
        error_pattern = self._extract_error_pattern(error_message)
        if not error_pattern:
            _logger.warning("Could not extract error pattern")
            return self.browse()
        
        # Check for duplicate
        existing = self.search([
            ('error_pattern', '=', error_pattern),
            ('model_name', '=', model_name),
        ], limit=1)
        
        if existing:
            # Update existing pattern with new success
            existing.write({
                'success_count': existing.success_count + 1,
                'verified': True,
                'verified_date': fields.Datetime.now(),
                'verified_by': self.env.user.id,
            })
            _logger.info(f"Updated existing pattern: {existing.name}")
            return existing
        
        # Create new pattern
        pattern = self.create({
            'name': f"Fix: {error_pattern[:60]}",
            'error_pattern': error_pattern,
            'model_name': model_name,
            'problem': problem,
            'solution': solution,
            'wrong_code': wrong_code,
            'correct_code': correct_code,
            'verified': True,
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
            'source': 'learned',
            'source_test_case_id': test_case.id if test_case else False,
            'source_error': error_message[:1000] if error_message else False,
            'success_count': 1,
        })
        
        _logger.info(f"Created verified pattern: {pattern.name}")
        return pattern

    def _extract_error_pattern(self, error_message):
        """Extract the key pattern from error message"""
        if not error_message:
            return None
        
        # Common patterns to extract
        patterns = [
            (r"Invalid field '(\w+)'", r"Invalid field '\1'"),
            (r"got an unexpected keyword argument '(\w+)'", r"unexpected keyword argument '\1'"),
            (r"No keyword with name '([^']+)'", r"No keyword with name"),
            (r"Wrong container value", "Wrong container value"),
            (r"(\w+) is required", r"\1 is required"),
            (r"Access Denied", "Access Denied"),
            (r"ValidationError", "ValidationError"),
        ]
        
        for regex, replacement in patterns:
            match = re.search(regex, error_message, re.IGNORECASE)
            if match:
                try:
                    return re.sub(regex, replacement, match.group(0), flags=re.IGNORECASE)
                except:
                    return match.group(0)
        
        # Fallback: first meaningful line
        for line in error_message.split('\n'):
            line = line.strip()
            if line and len(line) > 10 and not line.startswith('#'):
                return line[:100]
        
        return None
