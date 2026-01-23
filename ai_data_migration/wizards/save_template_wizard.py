from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MigrationSaveTemplateWizard(models.TransientModel):
    _name = 'migration.save.template.wizard'
    _description = 'Save Migration Template Wizard'

    project_id = fields.Many2one(
        'migration.project',
        string='Migration Project',
        required=True,
    )
    
    name = fields.Char(
        string='Template Name',
        required=True,
    )
    
    description = fields.Text(
        string='Description',
    )
    
    is_shared = fields.Boolean(
        string='Share with Team',
        default=False,
        help='Allow other users to use this template',
    )
    
    tag_ids = fields.Many2many(
        'migration.template.tag',
        string='Tags',
    )
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if 'project_id' in fields_list and self._context.get('default_project_id'):
            project = self.env['migration.project'].browse(self._context['default_project_id'])
            if project and 'name' in fields_list:
                res['name'] = f"{project.target_model_id.name} Import Template"
        
        return res
    
    def action_save_template(self):
        """Save the configuration as a template."""
        self.ensure_one()
        
        if not self.project_id.mapping_ids:
            raise UserError(_('Cannot save template without any field mappings.'))
        
        template = self.env['migration.template'].create_from_project(
            self.project_id,
            self.name,
            self.description,
        )
        
        template.write({
            'is_shared': self.is_shared,
            'tag_ids': [(6, 0, self.tag_ids.ids)],
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Template Saved'),
                'message': _('Migration template "%s" has been saved.') % self.name,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'migration.template',
                    'res_id': template.id,
                    'view_mode': 'form',
                }
            }
        }


class MigrationTemplateMappingsWizard(models.TransientModel):
    _name = 'migration.template.mappings.wizard'
    _description = 'View Template Mappings'

    template_id = fields.Many2one(
        'migration.template',
        string='Template',
        required=True,
    )
    
    mappings_display = fields.Text(
        string='Mappings',
        readonly=True,
    )
