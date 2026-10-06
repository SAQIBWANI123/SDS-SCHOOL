from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

PAYMENT_METHODS = [
    ('cash', 'Cash'),
    ('bank', 'Bank Transfer'),
    ('card', 'Card'),
    ('cheque', 'Cheque'),
    ('online', 'Online'),
]
OPEN_FEE_STATES = ('posted', 'partially_paid')


class FeeHead(models.Model):
    _name = 'school.fee.head'
    _description = 'Fee Head / Type'

    name = fields.Char(string='Fee Head Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')


class FeeStructure(models.Model):
    _name = 'school.fee.structure'
    _description = 'Fee Structure'

    name = fields.Char(string='Structure Name', required=True)
    grade_id = fields.Many2one('school.grade', string='Grade Level', required=True)
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', required=True)
    line_ids = fields.One2many('school.fee.structure.line', 'structure_id', string='Fee Head Lines')
    total_amount = fields.Float(string='Total Fee', compute='_compute_total_amount', store=True)

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(line.amount for line in rec.line_ids)

    def action_generate_fees(self):
        """Open the bulk fee generation wizard for this structure."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Fee Statements'),
            'res_model': 'school.fee.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_structure_id': self.id},
        }


class FeeStructureLine(models.Model):
    _name = 'school.fee.structure.line'
    _description = 'Fee Structure Line'

    structure_id = fields.Many2one('school.fee.structure', string='Fee Structure', ondelete='cascade')
    fee_head_id = fields.Many2one('school.fee.head', string='Fee Head', required=True)
    amount = fields.Float(string='Amount', required=True, default=0.0)


class StudentFee(models.Model):
    _name = 'school.student.fee'
    _description = 'Student Fee Invoice / Statement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_invoice desc, id desc'

    name = fields.Char(string='Invoice No', readonly=True, copy=False, default='New')
    student_id = fields.Many2one('school.student', string='Student', required=True, tracking=True)
    class_id = fields.Many2one('school.class', related='student_id.class_id', string='Class / Section', store=True)
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', required=True)
    structure_id = fields.Many2one('school.fee.structure', string='Fee Structure', copy=False)
    date_invoice = fields.Date(string='Invoice Date', default=fields.Date.context_today, required=True)
    date_due = fields.Date(string='Due Date', required=True)

    line_ids = fields.One2many('school.student.fee.line', 'fee_id', string='Fee Breakdown')
    payment_ids = fields.One2many('school.fee.payment', 'fee_id', string='Payments', copy=False)
    payment_count = fields.Integer(string='Payment Count', compute='_compute_payment_count')

    amount_total = fields.Float(string='Total Amount', compute='_compute_amounts', store=True)
    amount_paid = fields.Float(string='Amount Paid', default=0.0, copy=False, readonly=True)
    amount_due = fields.Float(string='Amount Due', compute='_compute_amounts', store=True)

    is_overdue = fields.Boolean(string='Overdue', compute='_compute_overdue', search='_search_is_overdue')
    days_overdue = fields.Integer(string='Days Overdue', compute='_compute_overdue')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted / Invoiced'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('school.student.fee') or 'FEE/0001'
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'line_ids' in vals:
            self.filtered(lambda f: f.state in ('posted', 'partially_paid', 'paid'))._update_payment_state()
        return res

    @api.depends('line_ids.amount', 'amount_paid')
    def _compute_amounts(self):
        for rec in self:
            total = sum(line.amount for line in rec.line_ids)
            rec.amount_total = total
            rec.amount_due = max(total - rec.amount_paid, 0.0)

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends('state', 'date_due', 'amount_due')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            overdue = bool(
                rec.state in OPEN_FEE_STATES and rec.date_due
                and rec.date_due < today and rec.amount_due > 0
            )
            rec.is_overdue = overdue
            rec.days_overdue = (today - rec.date_due).days if overdue else 0

    def _search_is_overdue(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_("Unsupported search on the Overdue field."))
        today = fields.Date.context_today(self)
        domain = [
            ('state', 'in', list(OPEN_FEE_STATES)),
            ('date_due', '<', today),
            ('amount_due', '>', 0),
        ]
        if (operator == '=') == value:
            return domain
        return ['!', '&', '&'] + domain

    @api.constrains('date_invoice', 'date_due')
    def _check_dates(self):
        for rec in self:
            if rec.date_due and rec.date_invoice and rec.date_due < rec.date_invoice:
                raise ValidationError(_("The due date cannot be earlier than the invoice date."))

    def _update_payment_state(self):
        """Derive the payment state from the paid amount (never from the user)."""
        for rec in self:
            if rec.state not in ('posted', 'partially_paid', 'paid'):
                continue
            if rec.amount_total > 0 and float_is_zero(rec.amount_due, precision_digits=2):
                new_state = 'paid'
            elif rec.amount_paid > 0:
                new_state = 'partially_paid'
            else:
                new_state = 'posted'
            if new_state != rec.state:
                rec.state = new_state

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_post(self):
        for rec in self:
            if not rec.line_ids or rec.amount_total <= 0:
                raise UserError(_("Add at least one fee line with an amount before posting %s.", rec.name))
        self.write({'state': 'posted'})
        self._update_payment_state()

    def action_register_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'school.fee.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_fee_id': self.id},
        }

    def action_cancel(self):
        for rec in self:
            if rec.payment_ids:
                raise UserError(_("%s has recorded payments and cannot be cancelled.", rec.name))
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.payment_ids:
                raise UserError(_("%s has recorded payments and cannot be reset to draft.", rec.name))
        self.write({'state': 'draft'})

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments'),
            'res_model': 'school.fee.payment',
            'view_mode': 'list,form',
            'domain': [('fee_id', '=', self.id)],
            'context': {'default_fee_id': self.id},
        }

    def action_print_receipt(self):
        self.ensure_one()
        return self.env.ref('smartdesk_school_management.action_report_fee_receipt').report_action(self)


class SchoolFeePayment(models.Model):
    _name = 'school.fee.payment'
    _description = 'Fee Payment'
    _order = 'date desc, id desc'

    name = fields.Char(string='Receipt No', readonly=True, copy=False, default='New')
    fee_id = fields.Many2one('school.student.fee', string='Fee Statement', required=True,
                             ondelete='restrict', index=True)
    student_id = fields.Many2one('school.student', related='fee_id.student_id', string='Student', store=True)
    class_id = fields.Many2one('school.class', related='fee_id.class_id', string='Class / Section', store=True)
    date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)
    amount = fields.Float(string='Amount', required=True)
    method = fields.Selection(PAYMENT_METHODS, string='Method', default='cash', required=True)
    reference = fields.Char(string='Reference / Cheque No')
    note = fields.Char(string='Note')
    collected_by_id = fields.Many2one('res.users', string='Collected By',
                                      default=lambda self: self.env.user, readonly=True)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("The payment amount must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('school.fee.payment') or 'PAY/0001'
        payments = super().create(vals_list)
        by_fee = defaultdict(lambda: self.browse())
        for payment in payments:
            by_fee[payment.fee_id] |= payment
        for fee, fee_payments in by_fee.items():
            if fee.state not in OPEN_FEE_STATES:
                raise UserError(_("Payments can only be registered on posted fee statements (%s).", fee.name))
            total = sum(fee_payments.mapped('amount'))
            if float_compare(total, fee.amount_due, precision_digits=2) > 0:
                raise UserError(_(
                    "The payment (%(paid).2f) exceeds the balance due on %(fee)s (%(due).2f).",
                    paid=total, fee=fee.name, due=fee.amount_due,
                ))
            fee.amount_paid += total
            fee._update_payment_state()
            for payment in fee_payments:
                fee.message_post(body=_(
                    "Payment %(receipt)s of %(amount).2f received (%(method)s).",
                    receipt=payment.name, amount=payment.amount,
                    method=dict(PAYMENT_METHODS).get(payment.method, payment.method),
                ))
        return payments

    def write(self, vals):
        if {'amount', 'fee_id'} & set(vals):
            raise UserError(_("Recorded payments cannot be modified. Delete the payment and register it again."))
        return super().write(vals)

    def unlink(self):
        for payment in self:
            fee = payment.fee_id
            fee.amount_paid = max(fee.amount_paid - payment.amount, 0.0)
            fee._update_payment_state()
            fee.message_post(body=_("Payment %s was removed.", payment.name))
        return super().unlink()


class StudentFeeLine(models.Model):
    _name = 'school.student.fee.line'
    _description = 'Student Fee Line Item'

    fee_id = fields.Many2one('school.student.fee', string='Student Fee Invoice', ondelete='cascade')
    fee_head_id = fields.Many2one('school.fee.head', string='Fee Head', required=True)
    amount = fields.Float(string='Amount', required=True, default=0.0)
    remarks = fields.Char(string='Remarks')
