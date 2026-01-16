# -*- coding: utf-8 -*-
"""
Knowledge Base Mixin for AI Agents

This mixin provides easy access to the central Knowledge Base.
Any agent module can inherit this mixin to get KB capabilities.

Usage:
    class MyAgentModel(models.Model):
        _name = 'my.agent.model'
        _inherit = ['mail.thread', 'ai.kb.mixin']
        
        def my_method(self):
            # Get context for AI prompts
            context = self.kb_get_context('19.0', 'upgrade', ['sale.order'])
            
            # Record an error
            error_id = self.kb_record_error('19.0', 'robot_test', error_msg, wrong_code)
            
            # Record a fix (after human verification)
            self.kb_record_fix(error_id, correct_code, 'Explanation of fix')
"""

import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class KBMixin(models.AbstractModel):
    """
    Mixin providing Knowledge Base access for AI agents.
    
    Inherit this in any model that needs KB access:
        _inherit = ['ai.kb.mixin']
    """
    _name = 'ai.kb.mixin'
    _description = 'Knowledge Base Mixin for AI Agents'

    # =========================================================================
    # CONTEXT RETRIEVAL - For AI Prompts
    # =========================================================================
    
    def kb_get_context(self, odoo_version, task_type, models=None):
        """
        Get comprehensive context for AI prompt.
        
        Args:
            odoo_version: Target Odoo version (e.g., '19.0')
            task_type: 'upgrade', 'test', 'enhancement', 'general'
            models: Optional list of model names to focus on
        
        Returns:
            str: Formatted context for AI prompt
        """
        return self.env['ai.knowledge.service'].get_context(
            odoo_version, task_type, models
        )
    
    def kb_get_test_context(self, odoo_version, models=None, test_type='robot'):
        """
        Get context specifically for test generation.
        
        Args:
            odoo_version: Target Odoo version
            models: List of model names being tested
            test_type: 'robot' or 'python'
        
        Returns:
            str: Test-specific context including common errors, patterns
        """
        return self.env['ai.knowledge.service'].get_test_context(
            odoo_version, models, test_type
        )
    
    def kb_get_upgrade_context(self, from_version, to_version, models=None):
        """
        Get context for upgrade/migration tasks.
        
        Args:
            from_version: Source Odoo version (e.g., '15.0')
            to_version: Target Odoo version (e.g., '19.0')
            models: List of model names being upgraded
        
        Returns:
            str: Breaking changes, migration patterns, etc.
        """
        return self.env['ai.knowledge.service'].get_upgrade_context(
            from_version, to_version, models
        )

    # =========================================================================
    # ERROR PATTERN QUERIES
    # =========================================================================
    
    def kb_get_error_patterns(self, error_message, task_type=None, 
                               model_name=None, odoo_version=None, limit=5):
        """
        Find matching error patterns for a given error.
        
        Args:
            error_message: The error text to match
            task_type: Optional filter ('robot_test', 'python_test', 'upgrade')
            model_name: Optional model name filter
            odoo_version: Optional version filter
            limit: Max patterns to return
        
        Returns:
            str: Formatted patterns for AI prompt
        """
        return self.env['ai.knowledge.service'].get_error_context(
            error_message, task_type, model_name, odoo_version, limit
        )
    
    def kb_search_errors(self, error_message, task_type=None, 
                          model_name=None, resolved_only=True):
        """
        Search for error pattern records.
        
        Args:
            error_message: Error text to search
            task_type: Filter by task type
            model_name: Filter by model
            resolved_only: Only return resolved errors with fixes
        
        Returns:
            recordset: ai.error.pattern records
        """
        ErrorPattern = self.env['ai.error.pattern']
        
        domain = []
        if resolved_only:
            domain.append(('resolved', '=', True))
        if task_type:
            domain.append(('task_type', '=', task_type))
        if model_name:
            domain.append(('model_name', '=', model_name))
        
        # Search by error text similarity
        patterns = ErrorPattern.search(domain, limit=50, order='occurrences desc')
        
        if error_message:
            error_lower = error_message.lower()
            patterns = patterns.filtered(
                lambda p: p.error_message and 
                any(word in error_lower 
                    for word in p.error_message.lower().split()[:5]
                    if len(word) > 3)
            )
        
        return patterns[:10]

    # =========================================================================
    # ERROR RECORDING - Write to KB
    # =========================================================================
    
    def kb_record_error(self, odoo_version, task_type, error_text, 
                         wrong_code=None, model_name=None):
        """
        Record a new error to the Knowledge Base.
        
        Call this when an error occurs. Later, when fixed and verified,
        call kb_record_fix() to complete the pattern.
        
        Args:
            odoo_version: Odoo version where error occurred
            task_type: 'robot_test', 'python_test', 'upgrade', etc.
            error_text: The error message/traceback
            wrong_code: The code that caused the error
            model_name: Optional model name involved
        
        Returns:
            int: ID of created error pattern, or None if failed
        """
        try:
            error = self.env['ai.knowledge.service'].record_error(
                odoo_version, task_type, error_text, wrong_code, model_name
            )
            if error:
                _logger.info(f"KB: Recorded error {error.id}")
                return error.id
        except Exception as e:
            _logger.warning(f"KB: Failed to record error: {e}")
        return None
    
    def kb_record_fix(self, error_id, correct_code, explanation=None):
        """
        Record a verified fix for an error.
        
        IMPORTANT: Only call this AFTER the fix has been verified
        (e.g., test passed, upgrade succeeded, human approved).
        
        Args:
            error_id: ID of the error pattern to update
            correct_code: The working code that fixes the error
            explanation: Optional explanation of why this fix works
        
        Returns:
            bool: True if successful
        """
        try:
            success = self.env['ai.knowledge.service'].record_fix(
                error_id, correct_code, explanation
            )
            if success:
                _logger.info(f"KB: Recorded fix for error {error_id}")
            return success
        except Exception as e:
            _logger.warning(f"KB: Failed to record fix: {e}")
            return False

    # =========================================================================
    # CODE PATTERNS
    # =========================================================================
    
    def kb_get_code_patterns(self, category=None, odoo_version=None, limit=5):
        """
        Get code patterns/templates.
        
        Args:
            category: 'model', 'view', 'controller', 'wizard', etc.
            odoo_version: Filter by version
            limit: Max patterns to return
        
        Returns:
            str: Formatted patterns for AI prompt
        """
        Pattern = self.env['ai.code.pattern']
        
        domain = [('active', '=', True)]
        if category:
            domain.append(('category', '=', category))
        if odoo_version:
            domain.append('|')
            domain.append(('odoo_version', '=', odoo_version))
            domain.append(('odoo_version', '=', 'all'))
        
        patterns = Pattern.search(domain, limit=limit)
        
        if not patterns:
            return ""
        
        result = "\n## CODE PATTERNS:\n"
        for p in patterns:
            result += f"\n### {p.name}\n"
            if p.description:
                result += f"{p.description}\n"
            result += f"```python\n{p.code_template}\n```\n"
        
        return result

    # =========================================================================
    # BREAKING CHANGES
    # =========================================================================
    
    def kb_get_breaking_changes(self, from_version, to_version, 
                                 category=None, model_name=None):
        """
        Get breaking changes between versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            category: Optional filter ('field', 'method', 'view', etc.)
            model_name: Optional model name filter
        
        Returns:
            recordset: ai.breaking.change records
        """
        BreakingChange = self.env['ai.breaking.change']
        
        domain = [
            ('from_version', '<=', from_version),
            ('to_version', '>=', to_version),
        ]
        
        if category:
            domain.append(('category', '=', category))
        if model_name:
            domain.append(('model_name', '=', model_name))
        
        return BreakingChange.search(domain, order='to_version desc')

    # =========================================================================
    # MODEL SCHEMAS
    # =========================================================================
    
    def kb_get_model_schema(self, model_name, odoo_version):
        """
        Get model schema (field definitions).
        
        Args:
            model_name: Odoo model name (e.g., 'sale.order')
            odoo_version: Target Odoo version
        
        Returns:
            dict: Field definitions, or None if not found
        """
        Schema = self.env['ai.model.schema']
        schema = Schema.search([
            ('model_name', '=', model_name),
            ('odoo_version', '=', odoo_version),
        ], limit=1)
        
        if schema and schema.fields_json:
            import json
            try:
                return json.loads(schema.fields_json)
            except:
                pass
        return None

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================
    
    def kb_format_for_prompt(self, sections):
        """
        Format multiple KB sections into a single prompt block.
        
        Args:
            sections: List of (title, content) tuples
        
        Returns:
            str: Formatted prompt section
        """
        result = "\n" + "=" * 60 + "\n"
        result += "KNOWLEDGE BASE CONTEXT\n"
        result += "=" * 60 + "\n"
        
        for title, content in sections:
            if content and content.strip():
                result += f"\n## {title}\n{content}\n"
        
        return result
    
    def kb_is_available(self):
        """
        Check if Knowledge Base is available.
        
        Returns:
            bool: True if KB module is installed and accessible
        """
        try:
            self.env['ai.knowledge.service']
            return True
        except:
            return False
