from odoo import _, api, fields, models

class SchoolClass(models.Model):
    _name = 'school.class'
    _description = 'Class / Section'

    name = fields.Char(string='Class Name', compute='_compute_name', store=True)
    grade_id = fields.Many2one('school.grade', string='Grade Level', required=True)
    section = fields.Char(string='Section', required=True, default='A')
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', required=True)
    class_teacher_id = fields.Many2one('school.teacher', string='Class Teacher')
    room_number = fields.Char(string='Room / Hall Number')
    capacity = fields.Integer(string='Class Capacity', default=30)
    student_ids = fields.One2many('school.student', 'class_id', string='Enrolled Students')
    student_count = fields.Integer(string='Total Students', compute='_compute_student_count', store=True)
    subject_allocation_ids = fields.One2many('school.subject.allocation', 'class_id', string='Subject Allocations')

    @api.depends('grade_id.name', 'section', 'academic_year_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.grade_id and rec.section:
                year = f" ({rec.academic_year_id.name})" if rec.academic_year_id else ""
                rec.name = f"{rec.grade_id.name} - {rec.section}{year}"
            else:
                rec.name = "New Class"

    available_seats = fields.Integer(string='Available Seats', compute='_compute_available_seats')

    @api.depends('student_ids')
    def _compute_student_count(self):
        for rec in self:
            rec.student_count = len(rec.student_ids)

    @api.depends('student_count', 'capacity')
    def _compute_available_seats(self):
        for rec in self:
            rec.available_seats = max((rec.capacity or 0) - rec.student_count, 0)

    def action_view_students(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Students of %s', self.display_name),
            'res_model': 'school.student',
            'view_mode': 'kanban,list,form',
            'domain': [('class_id', '=', self.id)],
            'context': {'default_class_id': self.id, 'default_grade_id': self.grade_id.id},
        }
