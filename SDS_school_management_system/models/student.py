from collections import defaultdict
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SchoolStudent(models.Model):
    _name = 'school.student'
    _description = 'Student'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Student Name', required=True, tracking=True)
    student_id_code = fields.Char(string='Registration ID', copy=False, readonly=True, default='New')
    roll_number = fields.Char(string='Roll Number')
    date_of_birth = fields.Date(string='Date of Birth', required=True)
    age = fields.Integer(string='Age', compute='_compute_age')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender', default='male', required=True)
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-'),
    ], string='Blood Group')
    admission_date = fields.Date(string='Admission Date', default=fields.Date.today)

    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone / Mobile')
    street = fields.Char(string='Street Address')
    street2 = fields.Char(string='Street Address 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP Code')
    country_id = fields.Many2one('res.country', string='Country')
    image_1920 = fields.Image(string='Student Photo')

    grade_id = fields.Many2one('school.grade', string='Grade Level', required=True, tracking=True)
    class_id = fields.Many2one('school.class', string='Class / Section',
                               domain="[('grade_id', '=', grade_id)]", tracking=True)
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', tracking=True)

    parent_ids = fields.Many2many('school.parent', string='Parents / Guardians')
    primary_parent_id = fields.Many2one('school.parent', string='Primary Guardian')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('enrolled', 'Enrolled'),
        ('graduated', 'Graduated'),
        ('suspended', 'Suspended'),
    ], string='Status', default='draft', tracking=True)

    medical_notes = fields.Text(string='Medical Notes / Allergies')
    conduct_ids = fields.One2many('school.student.conduct', 'student_id', string='Conduct & Achievements')

    # Computed metrics for smart buttons
    attendance_percentage = fields.Float(
        string='Attendance %', compute='_compute_student_stats')
    total_fee_due = fields.Float(
        string='Fee Balance Due', compute='_compute_student_stats')
    books_borrowed_count = fields.Integer(
        string='Books Borrowed', compute='_compute_student_stats')
    exam_results_count = fields.Integer(
        string='Exam Results', compute='_compute_student_stats')
    conduct_score = fields.Integer(
        string='Conduct Score', compute='_compute_student_stats')

    # ------------------------------------------------------------------
    # Constraints & computes
    # ------------------------------------------------------------------
    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        today = fields.Date.context_today(self)
        for student in self:
            if student.date_of_birth and student.date_of_birth > today:
                raise ValidationError(_("The date of birth of %s cannot be in the future.", student.name))

    @api.constrains('class_id')
    def _check_class_capacity(self):
        for student in self:
            klass = student.class_id
            if klass and klass.capacity and klass.student_count > klass.capacity:
                raise ValidationError(_(
                    "Class %(class)s is full (capacity %(capacity)s).",
                    **{'class': klass.display_name, 'capacity': klass.capacity},
                ))

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for student in self:
            dob = student.date_of_birth
            if dob:
                student.age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            else:
                student.age = 0

    def _compute_student_stats(self):
        ids = [rid for rid in self._origin.ids if rid]
        attendance = defaultdict(lambda: [0, 0])
        due = defaultdict(float)
        books = defaultdict(int)
        results = defaultdict(int)
        conduct = defaultdict(int)
        if ids:
            lines = self.env['school.attendance.line']._read_group(
                [('student_id', 'in', ids), ('attendance_id.state', '=', 'done')],
                ['student_id', 'state'], ['__count'])
            for student, state, count in lines:
                attendance[student.id][1] += count
                if state in ('present', 'late', 'excused'):
                    attendance[student.id][0] += count
            fees = self.env['school.student.fee']._read_group(
                [('student_id', 'in', ids), ('state', 'in', ('posted', 'partially_paid'))],
                ['student_id'], ['amount_due:sum'])
            for student, amount in fees:
                due[student.id] = amount
            issues = self.env['school.library.issue']._read_group(
                [('student_id', 'in', ids), ('state', 'in', ('issued', 'overdue'))],
                ['student_id'], ['__count'])
            for student, count in issues:
                books[student.id] = count
            res = self.env['school.exam.result']._read_group(
                [('student_id', 'in', ids)], ['student_id'], ['__count'])
            for student, count in res:
                results[student.id] = count
            cond = self.env['school.student.conduct']._read_group(
                [('student_id', 'in', ids)], ['student_id'], ['points:sum'])
            for student, points in cond:
                conduct[student.id] = points
        for student in self:
            rid = student._origin.id
            present, total = attendance[rid] if rid else (0, 0)
            student.attendance_percentage = round(present * 100.0 / total, 1) if total else 100.0
            student.total_fee_due = due[rid] if rid else 0.0
            student.books_borrowed_count = books[rid] if rid else 0
            student.exam_results_count = results[rid] if rid else 0
            student.conduct_score = conduct[rid] if rid else 0

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('student_id_code', 'New') == 'New':
                vals['student_id_code'] = (
                    self.env['ir.sequence'].next_by_code('school.student') or 'STU/0001'
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_enroll(self):
        self.write({'state': 'enrolled'})

    def action_promote(self):
        """Open the promotion wizard for the selected student(s)."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Promote Students'),
            'res_model': 'school.promote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_ids': [(6, 0, self.ids)],
                'default_from_class_id': self[:1].class_id.id if len(self) == 1 else False,
            },
        }

    def action_graduate(self):
        self.write({'state': 'graduated'})

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_reinstate(self):
        self.write({'state': 'enrolled'})

    def action_view_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance'),
            'res_model': 'school.attendance.line',
            'view_mode': 'list',
            'domain': [('student_id', '=', self.id)],
        }

    def action_view_fees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fee Statements'),
            'res_model': 'school.student.fee',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_view_books(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Books Issued'),
            'res_model': 'school.library.issue',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id), ('state', 'in', ('issued', 'overdue'))],
        }

    def action_view_exam_results(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Results'),
            'res_model': 'school.exam.result',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
        }
