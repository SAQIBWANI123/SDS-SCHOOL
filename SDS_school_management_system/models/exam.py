from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class GradeScale(models.Model):
    _name = 'school.grade.scale'
    _description = 'Grade Scale System'
    _order = 'min_per desc'

    name = fields.Char(string='Grade Letter', required=True)  # e.g. A+, A, B, C, F
    min_per = fields.Float(string='Minimum %', required=True)
    max_per = fields.Float(string='Maximum %', required=True)
    gpa = fields.Float(string='GPA Points', required=True)  # e.g. 4.0, 3.5
    remarks = fields.Char(string='Remarks / Evaluation')  # e.g. Outstanding, Excellent, Pass, Fail

    @api.constrains('min_per', 'max_per')
    def _check_range(self):
        for rec in self:
            if rec.min_per > rec.max_per:
                raise ValidationError(_("Minimum % cannot be greater than Maximum % for grade %s.", rec.name))


class SchoolExam(models.Model):
    _name = 'school.exam'
    _description = 'School Examination'
    _order = 'date_start desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Exam Name', required=True, tracking=True)  # e.g. Midterm 2026
    code = fields.Char(string='Exam Code', readonly=True, copy=False, default='New')
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', required=True)
    term_id = fields.Many2one('school.academic.term', string='Term',
                              domain="[('academic_year_id', '=', academic_year_id)]")
    grade_id = fields.Many2one('school.grade', string='Grade Level', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', tracking=True)
    description = fields.Text(string='Instructions / Notes')
    result_ids = fields.One2many('school.exam.result', 'exam_id', string='Report Cards')
    result_count = fields.Integer(string='Report Card Count', compute='_compute_result_stats')
    pass_rate = fields.Float(string='Pass Rate (%)', compute='_compute_result_stats')
    average_percentage = fields.Float(string='Average (%)', compute='_compute_result_stats')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("The exam end date cannot be before its start date."))

    @api.depends('result_ids.overall_result', 'result_ids.percentage')
    def _compute_result_stats(self):
        for rec in self:
            results = rec.result_ids
            rec.result_count = len(results)
            if results:
                rec.pass_rate = round(len(results.filtered(lambda r: r.overall_result == 'pass')) * 100.0 / len(results), 1)
                rec.average_percentage = round(sum(results.mapped('percentage')) / len(results), 1)
            else:
                rec.pass_rate = 0.0
                rec.average_percentage = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('school.exam') or 'EXM/0001'
        return super().create(vals_list)

    # Workflow --------------------------------------------------------
    def action_start(self):
        self.write({'state': 'ongoing'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_generate_report_cards(self):
        """Create one empty report card (with the grade's subjects) per enrolled student."""
        self.ensure_one()
        Result = self.env['school.exam.result']
        students = self.env['school.student'].search([
            ('grade_id', '=', self.grade_id.id), ('state', '=', 'enrolled'),
        ])
        existing = Result.search([('exam_id', '=', self.id)]).mapped('student_id')
        created = Result
        for student in students - existing:
            result = Result.create({'exam_id': self.id, 'student_id': student.id})
            result.action_generate_lines()
            created |= result
        message = _("%(created)s report card(s) created, %(skipped)s already existed.",
                    created=len(created), skipped=len(students & existing))
        if not students:
            message = _("No enrolled students found in %s.", self.grade_id.display_name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Report cards"),
                'message': message,
                'type': 'success' if created else 'warning',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_view_results(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Report Cards'),
            'res_model': 'school.exam.result',
            'view_mode': 'list,form',
            'domain': [('exam_id', '=', self.id)],
            'context': {'default_exam_id': self.id},
        }


class ExamResult(models.Model):
    _name = 'school.exam.result'
    _description = 'Student Exam Report Card'
    _order = 'exam_id, student_id'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    exam_id = fields.Many2one('school.exam', string='Exam', required=True)
    student_id = fields.Many2one('school.student', string='Student', required=True)
    class_id = fields.Many2one('school.class', string='Class / Section', related='student_id.class_id', store=True)
    line_ids = fields.One2many('school.exam.result.line', 'result_id', string='Subject Marks')

    total_max_marks = fields.Float(string='Total Max Marks', compute='_compute_scores', store=True)
    total_obtained_marks = fields.Float(string='Total Obtained Marks', compute='_compute_scores', store=True)
    percentage = fields.Float(string='Percentage (%)', compute='_compute_scores', store=True)
    final_grade = fields.Char(string='Grade Letter', compute='_compute_scores', store=True)
    overall_result = fields.Selection([
        ('pass', 'Passed'),
        ('fail', 'Failed'),
    ], string='Result Status', compute='_compute_scores', store=True)
    rank = fields.Integer(string='Rank in Exam', compute='_compute_rank',
                          help="Position among all report cards of this exam, ordered by percentage.")
    teacher_comments = fields.Text(string='Teacher Comments')

    @api.constrains('exam_id', 'student_id')
    def _check_unique_result(self):
        for rec in self:
            if self.search_count([
                ('id', '!=', rec.id), ('exam_id', '=', rec.exam_id.id), ('student_id', '=', rec.student_id.id),
            ]):
                raise ValidationError(_(
                    "%(student)s already has a report card for %(exam)s.",
                    student=rec.student_id.name, exam=rec.exam_id.name,
                ))

    @api.depends('exam_id.name', 'student_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.exam_id and rec.student_id:
                rec.name = f"Report Card: {rec.student_id.name} - {rec.exam_id.name}"
            else:
                rec.name = "New Exam Result"

    @api.depends('line_ids.obtained_marks', 'line_ids.max_marks', 'line_ids.result')
    def _compute_scores(self):
        scales = self.env['school.grade.scale'].search([])
        for rec in self:
            tot_max = sum(line.max_marks for line in rec.line_ids)
            tot_obt = sum(line.obtained_marks for line in rec.line_ids)
            rec.total_max_marks = tot_max
            rec.total_obtained_marks = tot_obt
            per = (tot_obt / tot_max * 100.0) if tot_max > 0 else 0.0
            rec.percentage = per

            scale = scales.filtered(lambda s: s.min_per <= per <= s.max_per)[:1]
            rec.final_grade = scale.name if scale else ('F' if per < 40 else 'A')

            # Overall pass if no subject line failed
            has_failed_line = any(line.result == 'fail' for line in rec.line_ids)
            rec.overall_result = 'fail' if has_failed_line else 'pass'

    @api.depends('percentage', 'exam_id')
    def _compute_rank(self):
        for rec in self:
            if not rec.exam_id or not rec._origin.id:
                rec.rank = 0
                continue
            better = self.search_count([
                ('exam_id', '=', rec.exam_id.id),
                ('percentage', '>', rec.percentage),
            ])
            rec.rank = better + 1

    def action_generate_lines(self):
        self.ensure_one()
        if not self.student_id or not self.student_id.grade_id:
            return
        self.line_ids.unlink()
        subjects = self.student_id.grade_id.subject_ids
        lines = []
        for sub in subjects:
            lines.append((0, 0, {
                'subject_id': sub.id,
                'max_marks': sub.max_mark or 100.0,
                'pass_marks': sub.pass_mark or 40.0,
                'obtained_marks': 0.0,
            }))
        self.write({'line_ids': lines})


class ExamResultLine(models.Model):
    _name = 'school.exam.result.line'
    _description = 'Exam Result Marks Line'

    result_id = fields.Many2one('school.exam.result', string='Report Card', ondelete='cascade')
    subject_id = fields.Many2one('school.subject', string='Subject', required=True)
    max_marks = fields.Float(string='Max Marks', default=100.0)
    pass_marks = fields.Float(string='Pass Marks', default=40.0)
    obtained_marks = fields.Float(string='Obtained Marks', default=0.0)
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ], string='Status', compute='_compute_line_result', store=True)

    @api.constrains('obtained_marks', 'max_marks')
    def _check_marks(self):
        for rec in self:
            if rec.obtained_marks < 0:
                raise ValidationError(_("Obtained marks cannot be negative."))
            if float_compare(rec.obtained_marks, rec.max_marks, precision_digits=2) > 0:
                raise ValidationError(_(
                    "Obtained marks (%(obtained)s) cannot exceed the maximum marks (%(max)s) for %(subject)s.",
                    obtained=rec.obtained_marks, max=rec.max_marks, subject=rec.subject_id.name,
                ))

    @api.depends('obtained_marks', 'pass_marks')
    def _compute_line_result(self):
        for rec in self:
            rec.result = 'pass' if rec.obtained_marks >= rec.pass_marks else 'fail'
