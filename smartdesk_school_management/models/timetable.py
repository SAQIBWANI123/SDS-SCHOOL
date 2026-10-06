from odoo import models, fields, api

class SchoolTimetable(models.Model):
    _name = 'school.timetable'
    _description = 'Class Timetable'

    name = fields.Char(string='Schedule Name', compute='_compute_name', store=True)
    class_id = fields.Many2one('school.class', string='Class / Section', required=True)
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', required=True)
    term_id = fields.Many2one('school.academic.term', string='Term')
    active = fields.Boolean(string='Active', default=True)
    line_ids = fields.One2many('school.timetable.line', 'timetable_id', string='Schedule Entries')

    @api.depends('class_id.name', 'academic_year_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.class_id and rec.academic_year_id:
                rec.name = f"Timetable: {rec.class_id.name} ({rec.academic_year_id.name})"
            else:
                rec.name = "New Timetable"


class SchoolTimetableLine(models.Model):
    _name = 'school.timetable.line'
    _description = 'Timetable Line Entry'
    _order = 'day_of_week, period_number'

    timetable_id = fields.Many2one('school.timetable', string='Timetable', ondelete='cascade')
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
    ], string='Day', required=True, default='0')
    period_number = fields.Selection([
        ('p1', 'Period 1 (08:30 - 09:15)'),
        ('p2', 'Period 2 (09:15 - 10:00)'),
        ('p3', 'Period 3 (10:15 - 11:00)'),
        ('p4', 'Period 4 (11:00 - 11:45)'),
        ('p5', 'Period 5 (12:30 - 01:15)'),
        ('p6', 'Period 6 (01:15 - 02:00)'),
        ('p7', 'Period 7 (02:00 - 02:45)'),
    ], string='Period Slot', required=True, default='p1')
    subject_id = fields.Many2one('school.subject', string='Subject', required=True)
    teacher_id = fields.Many2one('school.teacher', string='Teacher', required=True)
    room_number = fields.Char(string='Room / Lab')
