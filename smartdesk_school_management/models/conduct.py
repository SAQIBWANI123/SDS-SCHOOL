from odoo import fields, models


class SchoolStudentConduct(models.Model):
    _name = 'school.student.conduct'
    _description = 'Student Conduct & Achievement'
    _order = 'date desc, id desc'

    name = fields.Char(string='Title', required=True)
    student_id = fields.Many2one('school.student', string='Student', required=True,
                                 ondelete='cascade', index=True)
    class_id = fields.Many2one('school.class', related='student_id.class_id',
                               string='Class / Section', store=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    type = fields.Selection([
        ('achievement', 'Achievement'),
        ('commendation', 'Commendation'),
        ('counselling', 'Counselling'),
        ('warning', 'Warning'),
        ('incident', 'Incident'),
    ], string='Type', default='achievement', required=True)
    points = fields.Integer(
        string='Points', default=5,
        help="Positive points reward good conduct, negative points record concerns. "
             "The sum is shown on the student profile as the conduct score.")
    description = fields.Text(string='Details')
    recorded_by_id = fields.Many2one('res.users', string='Recorded By',
                                     default=lambda self: self.env.user, readonly=True)
