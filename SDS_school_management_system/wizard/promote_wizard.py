from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PromoteWizard(models.TransientModel):
    _name = 'school.promote.wizard'
    _description = 'Promote or Graduate Students'

    mode = fields.Selection([
        ('promote', 'Promote to another grade / class'),
        ('graduate', 'Mark as graduated'),
    ], string='Action', default='promote', required=True)
    from_class_id = fields.Many2one('school.class', string='Load Students of Class')
    student_ids = fields.Many2many('school.student', string='Students')
    target_grade_id = fields.Many2one('school.grade', string='New Grade Level')
    target_class_id = fields.Many2one('school.class', string='New Class / Section',
                                      domain="[('grade_id', '=', target_grade_id)]")
    target_year_id = fields.Many2one('school.academic.year', string='New Academic Year')

    @api.onchange('from_class_id')
    def _onchange_from_class_id(self):
        if self.from_class_id:
            self.student_ids = self.from_class_id.student_ids.filtered(lambda s: s.state == 'enrolled')

    @api.onchange('target_grade_id')
    def _onchange_target_grade_id(self):
        if self.target_class_id and self.target_class_id.grade_id != self.target_grade_id:
            self.target_class_id = False

    def action_apply(self):
        self.ensure_one()
        students = self.student_ids
        if not students:
            raise UserError(_("Select at least one student."))
        if self.mode == 'graduate':
            for student in students:
                student.message_post(body=_("Marked as graduated."))
            students.action_graduate()
            message = _("%s student(s) graduated.", len(students))
        else:
            if not self.target_grade_id:
                raise UserError(_("Choose the new grade level."))
            klass = self.target_class_id
            if klass and klass.capacity and klass.student_count + len(students - klass.student_ids) > klass.capacity:
                raise UserError(_("%(cls)s only has %(seats)s free seat(s) for %(n)s student(s).",
                                  cls=klass.display_name, seats=klass.available_seats, n=len(students)))
            for student in students:
                student.message_post(body=_(
                    "Promoted from %(old)s to %(new)s.",
                    old=student.class_id.display_name or student.grade_id.display_name,
                    new=klass.display_name or self.target_grade_id.display_name))
            vals = {'grade_id': self.target_grade_id.id, 'class_id': klass.id or False}
            if self.target_year_id:
                vals['academic_year_id'] = self.target_year_id.id
            students.write(vals)
            message = _("%s student(s) promoted.", len(students))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _("Done"), 'message': message, 'type': 'success',
                       'next': {'type': 'ir.actions.act_window_close'}},
        }
