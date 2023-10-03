from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    is_acquisition = fields.Boolean(default=False)
