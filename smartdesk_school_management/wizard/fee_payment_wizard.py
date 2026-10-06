from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.fee import PAYMENT_METHODS


class FeePaymentWizard(models.TransientModel):
    _name = 'school.fee.payment.wizard'
    _description = 'Register Fee Payment'

    fee_id = fields.Many2one('school.student.fee', string='Fee Statement', required=True)
    student_id = fields.Many2one(related='fee_id.student_id', string='Student')
    amount_total = fields.Float(related='fee_id.amount_total', string='Total')
    amount_due = fields.Float(related='fee_id.amount_due', string='Balance Due')
    amount = fields.Float(string='Amount Received', required=True)
    date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)
    method = fields.Selection(PAYMENT_METHODS, string='Method', default='cash', required=True)
    reference = fields.Char(string='Reference / Cheque No')
    note = fields.Char(string='Note')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        fee = self.env['school.student.fee'].browse(res.get('fee_id') or 0).exists()
        if fee and 'amount' in fields_list and not res.get('amount'):
            res['amount'] = fee.amount_due
        return res

    @api.onchange('fee_id')
    def _onchange_fee_id(self):
        if self.fee_id:
            self.amount = self.fee_id.amount_due

    def _create_payment(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Enter an amount greater than zero."))
        return self.env['school.fee.payment'].create({
            'fee_id': self.fee_id.id, 'amount': self.amount, 'date': self.date,
            'method': self.method, 'reference': self.reference, 'note': self.note,
        })

    def action_confirm(self):
        self._create_payment()
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm_print(self):
        self._create_payment()
        return self.fee_id.action_print_receipt()
