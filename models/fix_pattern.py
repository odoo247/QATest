# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class QAFixPattern(models.Model):
    """Store learned fix patterns to avoid repeating errors"""
    _name = 'qa.fix.pattern'
    _description = 'QA Fix Pattern'
    _order = 'use_count desc, id desc'

    name = fields.Char(string='Pattern Name', required=True)
    active = fields.Boolean(default=True)
    
    # Error matching
    error_pattern = fields.Char(string='Error Pattern', required=True,
                                help='Text pattern to match in error messages (case-insensitive)')
    error_type = fields.Selection([
        ('field_name', 'Invalid Field Name'),
        ('type_error', 'Type Mismatch'),
        ('missing_data', 'Missing Data'),
        ('permission', 'Permission Error'),
        ('validation', 'Validation Error'),
        ('keyword', 'Keyword Not Found'),
        ('other', 'Other'),
    ], string='Error Type', default='other')
    
    # Context
    model_name = fields.Char(string='Model', help='Odoo model this applies to (optional)')
    odoo_version = fields.Char(string='Odoo Version', help='Specific version (e.g., 17.0, 18.0) or empty for all')
    
    # The fix
    problem_description = fields.Text(string='Problem', required=True,
                                      help='What causes this error')
    solution_description = fields.Text(string='Solution', required=True,
                                       help='How to fix it')
    
    # Code examples
    wrong_code = fields.Text(string='Wrong Code Example',
                             help='Example of code that causes this error')
    correct_code = fields.Text(string='Correct Code Example',
                               help='Example of correct code')
    
    # Usage tracking
    use_count = fields.Integer(string='Times Used', default=0, readonly=True)
    success_count = fields.Integer(string='Successful Fixes', default=0, readonly=True)
    last_used = fields.Datetime(string='Last Used', readonly=True)
    
    # Source
    source = fields.Selection([
        ('manual', 'Manually Added'),
        ('learned', 'Learned from Fix'),
        ('system', 'System Default'),
    ], string='Source', default='manual')
    
    # Link to original fix if learned
    original_test_case_id = fields.Many2one('qa.test.case', string='Original Test Case')
    original_error = fields.Text(string='Original Error Message')

    _sql_constraints = [
        ('error_pattern_unique', 'unique(error_pattern, model_name)', 
         'Error pattern must be unique per model!')
    ]

    @api.model
    def find_matching_patterns(self, error_message, model_name=None, odoo_version=None):
        """
        Find fix patterns that match the given error
        
        Args:
            error_message: The error message to match
            model_name: Optional model name to filter by
            odoo_version: Optional Odoo version
        
        Returns:
            Recordset of matching patterns, ordered by relevance
        """
        if not error_message:
            return self.browse()
        
        error_lower = error_message.lower()
        
        # Build domain
        domain = [('active', '=', True)]
        
        # Search all patterns and filter by match
        all_patterns = self.search(domain, order='use_count desc')
        
        matching = self.browse()
        for pattern in all_patterns:
            # Check error pattern match
            if pattern.error_pattern.lower() in error_lower:
                # Check model match (if specified)
                if pattern.model_name and model_name:
                    if pattern.model_name != model_name:
                        continue
                
                # Check version match (if specified)
                if pattern.odoo_version and odoo_version:
                    if not odoo_version.startswith(pattern.odoo_version):
                        continue
                
                matching |= pattern
        
        return matching

    @api.model
    def get_patterns_for_prompt(self, error_message=None, model_name=None, limit=10):
        """
        Get fix patterns formatted for AI prompt
        
        Returns:
            String with formatted patterns for inclusion in prompt
        """
        if error_message:
            patterns = self.find_matching_patterns(error_message, model_name)[:limit]
        else:
            # Get most used patterns
            patterns = self.search([('active', '=', True)], order='use_count desc', limit=limit)
        
        if not patterns:
            return ""
        
        result = "\n## LEARNED FIX PATTERNS (from previous successful fixes):\n\n"
        
        for p in patterns:
            result += f"### {p.name}\n"
            result += f"**Error Pattern:** `{p.error_pattern}`\n"
            if p.model_name:
                result += f"**Model:** {p.model_name}\n"
            result += f"**Problem:** {p.problem_description}\n"
            result += f"**Solution:** {p.solution_description}\n"
            
            if p.wrong_code:
                result += f"**Wrong:**\n```robot\n{p.wrong_code}\n```\n"
            if p.correct_code:
                result += f"**Correct:**\n```robot\n{p.correct_code}\n```\n"
            
            result += "\n"
        
        return result

    def action_increment_use(self):
        """Increment use count"""
        for record in self:
            record.write({
                'use_count': record.use_count + 1,
                'last_used': fields.Datetime.now(),
            })

    def action_mark_success(self):
        """Mark pattern as successfully used"""
        for record in self:
            record.write({
                'success_count': record.success_count + 1,
            })

    @api.model
    def create_from_fix(self, test_case, error_message, fix_description, wrong_code=None, correct_code=None):
        """
        Create a new pattern from a successful fix
        
        Args:
            test_case: The test case that was fixed
            error_message: Original error message
            fix_description: Description of what was fixed
            wrong_code: Example of wrong code (optional)
            correct_code: Example of correct code (optional)
        
        Returns:
            Created pattern record
        """
        # Extract error pattern (first meaningful part of error)
        error_pattern = self._extract_error_pattern(error_message)
        
        if not error_pattern:
            return self.browse()
        
        # Check if pattern already exists
        existing = self.search([('error_pattern', '=', error_pattern)], limit=1)
        if existing:
            existing.action_increment_use()
            return existing
        
        # Extract model name from test case if possible
        model_name = None
        if test_case.robot_code:
            # Try to find model in code
            import re
            model_match = re.search(r"Create Record\s+(\w+\.\w+)", test_case.robot_code)
            if model_match:
                model_name = model_match.group(1)
        
        # Create new pattern
        pattern = self.create({
            'name': f"Fix: {error_pattern[:50]}",
            'error_pattern': error_pattern,
            'error_type': self._classify_error(error_message),
            'model_name': model_name,
            'problem_description': f"Error occurred: {error_message[:500]}",
            'solution_description': fix_description,
            'wrong_code': wrong_code,
            'correct_code': correct_code,
            'source': 'learned',
            'original_test_case_id': test_case.id,
            'original_error': error_message,
            'use_count': 1,
            'last_used': fields.Datetime.now(),
        })
        
        _logger.info(f"Created fix pattern: {pattern.name}")
        return pattern

    def _extract_error_pattern(self, error_message):
        """Extract the key pattern from an error message"""
        if not error_message:
            return None
        
        # Common patterns to extract
        import re
        
        patterns = [
            r"Invalid field '(\w+)'",  # Invalid field 'xxx'
            r"No keyword with name '([^']+)'",  # Keyword not found
            r"got an unexpected keyword argument '(\w+)'",  # Unexpected argument
            r"Wrong container value",  # Type error
            r"(\w+) is required",  # Required field
            r"Access Denied",  # Permission
            r"No (\w+) found",  # Missing data
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # Fallback: first line up to 100 chars
        first_line = error_message.split('\n')[0][:100]
        return first_line.strip()

    def _classify_error(self, error_message):
        """Classify error type based on message"""
        error_lower = error_message.lower()
        
        if 'invalid field' in error_lower:
            return 'field_name'
        elif 'wrong container' in error_lower or 'type' in error_lower:
            return 'type_error'
        elif 'no keyword' in error_lower:
            return 'keyword'
        elif 'not found' in error_lower or 'no ' in error_lower:
            return 'missing_data'
        elif 'access' in error_lower or 'permission' in error_lower:
            return 'permission'
        elif 'required' in error_lower or 'validation' in error_lower:
            return 'validation'
        else:
            return 'other'
