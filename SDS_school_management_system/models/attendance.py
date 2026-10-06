from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SchoolAttendance(models.Model):
    _name = 'school.attendance'
    _description = 'Class Attendance Register'
    _order = 'date desc, class_id'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    date = fields.Date(string='Attendance Date', default=fields.Date.context_today, required=True)
    class_id = fields.Many2one('school.class', string='Class / Section', required=True)
    teacher_id = fields.Many2one('school.teacher', string='Teacher / Staff', required=True)
    line_ids = fields.One2many('school.attendance.line', 'attendance_id', string='Student Attendance Records')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Submitted'),
    ], string='Status', default='draft', required=True)

    present_count = fields.Integer(string='Present Count', compute='_compute_counts')
    absent_count = fields.Integer(string='Absent Count', compute='_compute_counts')
    pending_count = fields.Integer(string='Not Marked', compute='_compute_counts')
    attendance_rate = fields.Float(string='Attendance Rate (%)', compute='_compute_counts')

    @staticmethod
    def _clean_line_commands(vals):
        commands = vals.get('line_ids')
        if not commands:
            return vals
        vals['line_ids'] = [
            command for command in commands
            if command[0] != 0 or command[2].get('student_id')
        ]
        return vals

    @staticmethod
    def _roster_commands(class_record):
        return [
            (0, 0, {'student_id': student.id})
            for student in class_record.student_ids
        ]

    @api.model_create_multi
    def create(self, vals_list):
        cleaned_vals_list = []
        for vals in vals_list:
            vals = self._clean_line_commands(vals)
            if vals.get('class_id') and not vals.get('line_ids'):
                class_record = self.env['school.class'].browse(vals['class_id']).exists()
                vals['line_ids'] = self._roster_commands(class_record)
            cleaned_vals_list.append(vals)
        return super().create(cleaned_vals_list)

    def write(self, vals):
        return super().write(self._clean_line_commands(vals))

    @api.constrains('class_id', 'date')
    def _check_unique_register(self):
        for rec in self:
            duplicate = self.search_count([
                ('id', '!=', rec.id),
                ('class_id', '=', rec.class_id.id),
                ('date', '=', rec.date),
            ])
            if duplicate:
                raise ValidationError(_(
                    "An attendance register for %(class)s on %(date)s already exists.",
                    **{'class': rec.class_id.display_name, 'date': rec.date},
                ))

    @api.depends('class_id.name', 'date')
    def _compute_name(self):
        for rec in self:
            if rec.class_id and rec.date:
                rec.name = f"Attendance: {rec.class_id.name} ({rec.date})"
            else:
                rec.name = "New Attendance Record"

    @api.depends('line_ids.state')
    def _compute_counts(self):
        for rec in self:
            lines = rec.line_ids
            present = len(lines.filtered(lambda l: l.state in ('present', 'late')))
            excused = len(lines.filtered(lambda l: l.state == 'excused'))
            rec.present_count = present
            rec.absent_count = len(lines.filtered(lambda l: l.state in ('absent', 'leave')))
            rec.pending_count = len(lines.filtered(lambda l: not l.state))
            counted = len(lines) - excused
            rec.attendance_rate = round(present * 100.0 / counted, 1) if counted else 0.0

    @api.onchange('class_id')
    def _onchange_class_id(self):
        if not self.class_id:
            self.line_ids = [(5, 0, 0)]
            return
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, {'student_id': student.id})
            for student in self.class_id.student_ids
        ]

    def action_load_students(self):
        self.ensure_one()
        if not self.class_id:
            raise UserError(_("Please select a Class first."))
        self.line_ids.unlink()
        lines = [(0, 0, {'student_id': student.id}) for student in self.class_id.student_ids]
        self.write({'line_ids': lines})

    def action_mark_all_present(self):
        """Fast path for the common case: mark every student without a status as present."""
        for rec in self:
            rec.line_ids.filtered(lambda l: not l.state).write({'state': 'present'})

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("The register has no students. Load the class roster first."))
            missing_status = rec.line_ids.filtered(lambda line: not line.state)
            if missing_status:
                names = ', '.join(missing_status.mapped('student_id.name'))
                raise ValidationError(_("Please select an attendance status for: %s", names))
            missing_reasons = rec.line_ids.filtered(
                lambda line: line.state in ('absent', 'leave') and not line.absence_reason
            )
            if missing_reasons:
                names = ', '.join(missing_reasons.mapped('student_id.name'))
                raise ValidationError(_("Please enter an absence or leave reason for: %s", names))
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class SchoolAttendanceLine(models.Model):
    _name = 'school.attendance.line'
    _description = 'Student Attendance Line'
    _order = 'date desc, id'

    attendance_id = fields.Many2one('school.attendance', string='Attendance Register', ondelete='cascade')
    date = fields.Date(related='attendance_id.date', string='Date', store=True)
    class_id = fields.Many2one('school.class', related='attendance_id.class_id',
                               string='Class / Section', store=True)
    student_id = fields.Many2one('school.student', string='Student', required=True)
    roll_number = fields.Char(related='student_id.roll_number', string='Roll No')
    state = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'On Leave'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ], string='Attendance Status')
    absence_reason = fields.Char(string='Absence / Leave Reason')

    @api.model_create_multi
    def create(self, vals_list):
        valid_vals_list = [vals for vals in vals_list if vals.get('student_id')]
        return super().create(valid_vals_list) if valid_vals_list else self.browse()

    @api.constrains('state', 'absence_reason')
    def _check_absence_reason(self):
        for line in self:
            if line.state in ('absent', 'leave') and not line.absence_reason:
                raise ValidationError(_("An absence or leave reason is required for %s.", line.student_id.name))
