from odoo import api, fields, _, models, exceptions
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    employee_id = fields.Many2one('hr.employee', compute='_compute_employee_id', compute_sudo=True)
    employee_departament_id = fields.Many2one(related="employee_id.department_id")
    department_id = fields.Many2one('hr.department', domain='[("id", "=", employee_departament_id)]')
    is_acquisition = fields.Boolean(related='employee_id.department_id.is_acquisition')
    partner_id = fields.Many2one(required=False)
    request_user_id = fields.Many2one('res.partner')

    limit_config_id = fields.Many2one('purchase.limit.config', string='Configuración de Límite')
    current_limit = fields.Float(string='Límite Actual', related='limit_config_id.current_limit', store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('limit_approval', 'Autorización por Límite'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', track_visibility='onchange', copy=False, index=True, readonly=True, default='draft', required=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super(PurchaseOrder, self).default_get(fields_list)
        defaults['employee_id'] = self.env['hr.employee'].search([('user_id', '=', self.env.context.get('uid'))])
        return defaults

    def _compute_employee_id(self):
        for purchase_order_id in self:
            employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.context.get('uid'))], limit=1)
            if not employee_id:
                raise UserError(_('There is no employee related to this user.'))
            else:
                purchase_order_id.employee_id = employee_id

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if not val['user_id']:
                val['partner_id'] = self.env.user.partner_id.id
                val['request_user_id'] = self.env.user.partner_id.id
            employee_id = self.env['hr.employee'].search([('user_id', '=', val['user_id'])])
            if not employee_id:
                raise UserError(_('There is no employee related to this user.'))
            if not val['partner_id']:
                val['partner_id'] = self.env.user.partner_id.id
            if len(employee_id) == 1 and val['user_id']:
                val['employee_id'] = employee_id.id
            val['request_user_id'] = self.env.user.partner_id.id
        res = super().create(vals_list)
        return res

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        if self.partner_id == self.request_user_id:
            raise UserError(_('The provider cannot be the same as the requesting user, please correct.'))
        return res

    @api.model
    def create(self, vals):
        order = super(PurchaseOrder, self).create(vals)
        order.check_amount_limit()
        return order

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        if 'order_line' in vals or 'current_limit' in vals:
            self.check_amount_limit()
        return res

    @api.constrains('order_line')
    def check_amount_limit(self):
        for order in self:
            max_amount_limit = order.current_limit
            if max_amount_limit:
                order_amount = sum(line.price_unit * line.product_qty for line in order.order_line)
                if order_amount > max_amount_limit:
                    order.write({'state': 'limit_approval'})
                else:
                    order.write({'state': 'draft'})

    def action_approve_limit(self):
        for order in self:
            order._validate_limit_approval()
            order._check_manager_permission()
            order.write({'state': 'sent'})

    def _validate_limit_approval(self):
        for order in self:
            if order.state != 'limit_approval':
                raise UserError(_("La orden no está en estado 'Autorización por Límite'."))

    def _check_manager_permission(self):
        user = self.env.user
        if not user.has_group('purchase.group_purchase_manager'):
            raise UserError(_("Solo los administradores pueden aprobar la orden."))

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        for order in self:
            if 'state' in vals and vals['state'] == 'limit_approval':
                group = self.env.ref('purchase.group_purchase_manager')
                users = group.users

                for user in users:
                    self.env['mail.activity'].create({
                        'res_id': order.id,
                        'res_model_id': self.env.ref('purchase.model_purchase_order').id,
                        'summary': 'Revisar orden con límite de compra excedido',
                        'note': 'La orden de compra %s ha excedido el límite de compra.' % (order.name),
                        'user_id': user.id,
                    })
        return res