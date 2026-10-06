from odoo import _, fields, models

class SchoolParent(models.Model):
    _name = 'school.parent'
    _description = 'Parent / Guardian'
    _order = 'name'

    name = fields.Char(string='Guardian Name', required=True)
    relation_type = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Legal Guardian'),
    ], string='Relation Type', default='father', required=True)
    occupation = fields.Char(string='Occupation')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    user_id = fields.Many2one('res.users', string='Portal User', copy=False,
                               help='Portal account allowed to view this guardian\'s children and fee statements.')
    student_ids = fields.Many2many('school.student', string='Children / Wards')
    emergency_contact = fields.Boolean(string='Is Emergency Contact', default=True)

    def _children_action(self, name, model, extra_domain=None):
        self.ensure_one()
        domain = [('student_id', 'in', self.student_ids.ids)]
        if extra_domain:
            domain += extra_domain
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_view_children(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Children / Wards'),
            'res_model': 'school.student',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.student_ids.ids)],
        }

    def action_view_fees(self):
        return self._children_action(_('Children Fee Statements'), 'school.student.fee')

    def action_view_attendance(self):
        return self._children_action(_('Children Attendance'), 'school.attendance.line')

    def action_view_exam_results(self):
        return self._children_action(_('Children Exam Results'), 'school.exam.result')
