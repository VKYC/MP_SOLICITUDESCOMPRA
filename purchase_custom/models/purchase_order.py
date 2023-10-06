from odoo import api, fields, _, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    employee_id = fields.Many2one('hr.employee', compute='_compute_employee_id', compute_sudo=True, store=True)
    department_id = fields.Many2one('hr.department')
    is_acquisition = fields.Boolean(related='employee_id.department_id.is_acquisition')
    partner_id = fields.Many2one(required=False)

    @api.model
    def default_get(self, fields_list):
        defaults = super(PurchaseOrder, self).default_get(fields_list)
        defaults['employee_id'] = self.env['hr.employee'].search([('user_id', '=', self.env.context.get('uid'))])
        return defaults

    def _compute_employee_id(self):
        for purchase_order_id in self:
            employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.context.get('uid'))])
            if not employee_id:
                raise UserError(_('There is no employee related to this user.'))
            else:
                purchase_order_id.employee_id = employee_id

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            employee_id = self.env['hr.employee'].search([('user_id', '=', val['user_id'])])
            if not employee_id:
                raise UserError(_('There is no employee related to this user.'))
            if not val['partner_id']:
                val['partner_id'] = self.env.user.partner_id.id
            val['employee_id'] = employee_id.id
        res = super().create(vals_list)
        return res
