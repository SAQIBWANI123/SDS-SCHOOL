from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FeeGenerateWizard(models.TransientModel):
    _name = 'school.fee.generate.wizard'
    _description = 'Generate Fee Statements in Bulk'

    structure_id = fields.Many2one('school.fee.structure', string='Fee Structure', required=True)
    grade_id = fields.Many2one(related='structure_id.grade_id', string='Grade Level')
    academic_year_id = fields.Many2one(related='structure_id.academic_year_id', string='Academic Year')
    class_ids = fields.Many2many('school.class', string='Only These Classes',
                                 domain="[('grade_id', '=', grade_id)]",
                                 help="Leave empty to bill every enrolled student of the grade.")
    date_invoice = fields.Date(string='Invoice Date', default=fields.Date.context_today, required=True)
    date_due = fields.Date(string='Due Date', required=True,
                           default=lambda self: fields.Date.context_today(self) + timedelta(days=30))
    auto_post = fields.Boolean(string='Post Immediately', default=True)
    student_count = fields.Integer(string='Students to Bill', compute='_compute_student_count')

    def _get_students(self):
        self.ensure_one()
        domain = [('grade_id', '=', self.grade_id.id), ('state', '=', 'enrolled')]
        if self.class_ids:
            domain.append(('class_id', 'in', self.class_ids.ids))
        students = self.env['school.student'].search(domain)
        billed = self.env['school.student.fee'].search([
            ('structure_id', '=', self.structure_id.id), ('state', '!=', 'cancelled'),
        ]).mapped('student_id')
        return students - billed

    @api.depends('structure_id', 'class_ids')
    def _compute_student_count(self):
        for wiz in self:
            wiz.student_count = len(wiz._get_students()) if wiz.structure_id else 0

    def action_generate(self):
        self.ensure_one()
        if not self.structure_id.line_ids:
            raise UserError(_("The fee structure has no fee lines."))
        students = self._get_students()
        if not students:
            raise UserError(_("Nobody to bill: no enrolled students, or all of them already have this fee."))
        lines = [(0, 0, {'fee_head_id': l.fee_head_id.id, 'amount': l.amount})
                 for l in self.structure_id.line_ids]
        fees = self.env['school.student.fee'].create([{
            'student_id': s.id, 'academic_year_id': self.academic_year_id.id,
            'structure_id': self.structure_id.id, 'date_invoice': self.date_invoice,
            'date_due': self.date_due, 'line_ids': lines,
        } for s in students])
        if self.auto_post:
            fees.action_post()
        return {
            'type': 'ir.actions.act_window', 'name': _('Generated Fee Statements'),
            'res_model': 'school.student.fee', 'view_mode': 'list,form',
            'domain': [('id', 'in', fees.ids)],
        }
