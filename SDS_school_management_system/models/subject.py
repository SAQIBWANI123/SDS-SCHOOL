from odoo import models, fields

class SchoolSubject(models.Model):
    _name = 'school.subject'
    _description = 'Subject / Course'

    name = fields.Char(string='Subject Name', required=True)
    code = fields.Char(string='Subject Code', required=True)
    subject_type = fields.Selection([
        ('theory', 'Theory'),
        ('practical', 'Practical'),
        ('both', 'Theory & Practical'),
        ('elective', 'Elective'),
    ], string='Subject Type', default='both', required=True)
    pass_mark = fields.Float(string='Pass Mark', default=40.0)
    max_mark = fields.Float(string='Maximum Mark', default=100.0)
    description = fields.Text(string='Syllabus / Notes')
    teacher_ids = fields.Many2many('school.teacher', string='Qualified Teachers')


class SubjectAllocation(models.Model):
    _name = 'school.subject.allocation'
    _description = 'Class Subject Allocation'

    class_id = fields.Many2one('school.class', string='Class / Section', required=True, ondelete='cascade')
    subject_id = fields.Many2one('school.subject', string='Subject', required=True)
    teacher_id = fields.Many2one('school.teacher', string='Assigned Teacher', required=True)
    weekly_periods = fields.Integer(string='Periods per Week', default=4)
