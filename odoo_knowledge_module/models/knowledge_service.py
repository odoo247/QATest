# -*- coding: utf-8 -*-
from odoo import models, api


class AiKnowledgeService(models.AbstractModel):
    _name = 'ai.knowledge.service'
    _description = 'AI Knowledge Service'

    @api.model
    def get_context(self, odoo_version, task_type, models_list=None):
        """
        Get comprehensive context based on task type.
        
        Args:
            odoo_version: Target Odoo version
            task_type: 'upgrade', 'test', 'enhancement', 'consultant'
            models_list: Optional list of model names
        
        Returns:
            str: Formatted context for AI prompt
        """
        if task_type == 'upgrade':
            # For upgrade, we need from_version - assume one major version back
            major = int(odoo_version.split('.')[0])
            from_version = f"{major - 1}.0"
            return self.get_upgrade_context(from_version, odoo_version, models_list)
        elif task_type == 'test':
            return self.get_test_context(odoo_version, models_list)
        elif task_type == 'enhancement':
            return self.get_enhancement_context(odoo_version, models_list)
        elif task_type == 'consultant':
            return self.get_consultant_context('', odoo_version)
        else:
            return self.get_enhancement_context(odoo_version, models_list)

    @api.model
    def get_error_context(self, error_message, task_type=None, model_name=None, 
                          odoo_version=None, limit=5):
        """
        Get error patterns matching an error message, formatted for AI prompt.
        
        Args:
            error_message: The error text to match
            task_type: Optional filter by task type
            model_name: Optional filter by model
            odoo_version: Optional filter by version
            limit: Max patterns to return
        
        Returns:
            str: Formatted error patterns for AI prompt
        """
        if not error_message:
            return ""
        
        ErrorPattern = self.env['ai.error.pattern']
        
        domain = [('resolved', '=', True)]
        if task_type:
            domain.append(('task_type', '=', task_type))
        if model_name:
            domain.append(('model_name', '=', model_name))
        if odoo_version:
            domain.append('|')
            domain.append(('odoo_version', '=', odoo_version))
            domain.append(('odoo_version', '=', 'all'))
        
        patterns = ErrorPattern.search(domain, limit=50, order='occurrences desc')
        
        # Filter by error message similarity
        error_lower = error_message.lower()
        matching = patterns.filtered(
            lambda p: p.error_message and 
            any(word in error_lower 
                for word in p.error_message.lower().split()[:5]
                if len(word) > 3)
        )[:limit]
        
        if not matching:
            return ""
        
        result = "\n## KNOWN ERROR PATTERNS (verified fixes):\n"
        for p in matching:
            result += f"\n### Error: {p.error_type or 'Unknown'}\n"
            result += f"**Pattern:** `{p.error_message[:100]}...`\n"
            if p.wrong_code:
                result += f"**WRONG:**\n```\n{p.wrong_code[:300]}\n```\n"
            if p.correct_code:
                result += f"**CORRECT:**\n```\n{p.correct_code[:300]}\n```\n"
            if p.fix_explanation:
                result += f"**Why:** {p.fix_explanation}\n"
        
        return result

    @api.model
    def get_upgrade_context(self, from_version, to_version, models_list=None):
        """Get context for upgrade tasks."""
        sections = [f"# Upgrade Context: {from_version} → {to_version}\n"]
        
        changes = self.env['ai.breaking.change'].search([
            ('from_version', '>=', from_version),
            ('to_version', '<=', to_version),
        ], limit=20)
        if changes:
            sections.append("## Breaking Changes")
            sections.extend([c.to_context() for c in changes])
        
        if models_list:
            schemas = self.env['ai.model.schema'].search([
                ('model_name', 'in', models_list),
                ('odoo_version', '=', to_version),
            ])
            if schemas:
                sections.append("\n## Model Schemas")
                sections.extend([s.model_name + ": " + str(s.field_count) + " fields" for s in schemas])
        
        errors = self.env['ai.error.pattern'].search([
            ('odoo_version', '=', to_version),
            ('task_type', '=', 'upgrade'),
            ('resolved', '=', True),
        ], limit=10)
        if errors:
            sections.append("\n## Known Issues")
            for e in errors:
                sections.append(f"- {e.error_message[:50]}... → {e.fix_explanation or 'See correct_code'}")
        
        return '\n'.join(sections)

    @api.model
    def get_enhancement_context(self, version, models_list=None):
        """Get context for enhancement tasks."""
        sections = [f"# Enhancement Context: {version}\n"]
        
        if models_list:
            schemas = self.env['ai.model.schema'].search([
                ('model_name', 'in', models_list),
                ('odoo_version', '=', version),
            ])
            if schemas:
                sections.append("## Model Schemas")
                for s in schemas:
                    sections.append(f"- {s.model_name}: {s.field_count} fields")
        
        patterns = self.env['ai.code.pattern'].search([
            '|', ('odoo_version', '=', version), ('odoo_version', '=', 'all'),
        ], limit=10)
        if patterns:
            sections.append("\n## Code Patterns")
            sections.extend([p.to_context() for p in patterns])
        
        return '\n'.join(sections)

    @api.model
    def get_test_context(self, version, models_list=None, test_type='robot'):
        """Get context for test generation."""
        sections = [f"# Test Context: {version} ({test_type})\n"]
        
        errors = self.env['ai.error.pattern'].search([
            ('odoo_version', '=', version),
            ('task_type', 'in', ['robot_test', 'python_test']),
            ('resolved', '=', True),
        ], limit=10)
        if errors:
            sections.append("## Known Test Issues")
            for e in errors:
                sections.append(f"- Avoid: {e.error_message[:50]}...")
        
        if test_type == 'robot':
            sections.append("""
## Robot Best Practices
- Use @name for buttons: xpath=//button[@name='action_confirm']
- Avoid class-based locators
- Wait for elements after navigation""")
        
        return '\n'.join(sections)

    @api.model
    def get_consultant_context(self, requirement, version='19.0', edition='enterprise'):
        """Get context for solution design."""
        sections = [f"# Solution Design: {requirement[:50]}...\n"]
        
        features = self.env['ai.module.feature'].search([
            '|', ('keywords', 'ilike', requirement), ('name', 'ilike', requirement),
        ], limit=5)
        if features:
            sections.append("## Standard Features")
            sections.extend([f.to_context() for f in features])
        
        configs = self.env['ai.config.option'].search([
            '|', ('keywords', 'ilike', requirement), ('name', 'ilike', requirement),
        ], limit=5)
        if configs:
            sections.append("\n## Configuration Options")
            sections.extend([c.to_context() for c in configs])
        
        customs = self.env['ai.custom.pattern'].search([
            '|', ('keywords', 'ilike', requirement), ('name', 'ilike', requirement),
        ], limit=5)
        if customs:
            sections.append("\n## Customisation Patterns")
            sections.extend([c.to_context() for c in customs])
        
        limits = self.env['ai.limitation'].search([
            '|', ('keywords', 'ilike', requirement), ('limitation', 'ilike', requirement),
        ], limit=3)
        if limits:
            sections.append("\n## Limitations")
            sections.extend([l.to_context() for l in limits])
        
        return '\n'.join(sections)

    @api.model
    def quick_check(self, requirement):
        """Quick check: standard vs config vs custom."""
        # Check features
        feature = self.env['ai.module.feature'].search([
            '|', ('keywords', 'ilike', requirement), ('name', 'ilike', requirement),
        ], limit=1)
        if feature:
            return {'approach': 'standard', 'reason': f"Feature: {feature.name}", 
                    'hours': 1, 'modules': [feature.module]}
        
        # Check configs
        config = self.env['ai.config.option'].search([
            '|', ('keywords', 'ilike', requirement), ('name', 'ilike', requirement),
        ], limit=1)
        if config:
            return {'approach': 'configuration', 'reason': f"Config: {config.name}",
                    'hours': config.estimated_hours, 'modules': [config.module] if config.module else []}
        
        # Check customs
        custom = self.env['ai.custom.pattern'].search([
            '|', ('keywords', 'ilike', requirement), ('name', 'ilike', requirement),
        ], limit=1)
        if custom:
            return {'approach': 'customization', 'reason': f"Pattern: {custom.name}",
                    'hours': custom.estimated_days * 8, 'modules': []}
        
        return {'approach': 'customization', 'reason': 'No match found', 'hours': 0, 'modules': []}

    @api.model
    def record_error(self, version, task_type, error_text, wrong_code, model=None):
        """Record error for learning."""
        return self.env['ai.error.pattern'].record_error(version, task_type, error_text, wrong_code, model)

    @api.model
    def record_fix(self, error_id, correct_code, explanation=None):
        """Record fix for error."""
        error = self.env['ai.error.pattern'].browse(error_id)
        if error.exists():
            error.record_fix(correct_code, explanation)
            return True
        return False

    @api.model
    def extract_schema(self, model_name, version=None):
        """Extract schema from Odoo."""
        return self.env['ai.model.schema'].extract_from_odoo(model_name, version)
