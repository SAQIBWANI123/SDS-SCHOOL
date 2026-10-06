from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SchoolAdmission(models.Model):
    _name = 'school.admission'
    _description = 'School Admission Application'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Application Number', readonly=True, copy=False, default='New')
    student_name = fields.Char(required=True, tracking=True)
    date_of_birth = fields.Date(required=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), ('other', 'Other')], required=True)
    grade_id = fields.Many2one('school.grade', string='Grade Applying For', required=True, tracking=True)
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year')
    guardian_name = fields.Char(required=True)
    guardian_relation = fields.Char(string='Relationship')
    guardian_email = fields.Char(required=True)
    guardian_phone = fields.Char(required=True)
    address = fields.Text()
    document_ids = fields.Many2many('ir.attachment', string='Documents')
    notes = fields.Text()
    state = fields.Selection([
        ('new', 'New'),
        ('review', 'Under Review'),
        ('waitlist', 'Waitlisted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='new', required=True, tracking=True)
    reviewer_id = fields.Many2one('res.users', string='Reviewed By', readonly=True, copy=False)
    decision_date = fields.Date(string='Decision Date', readonly=True, copy=False)
    rejection_reason = fields.Char(string='Decision Note')
    student_id = fields.Many2one('school.student', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('school.admission') or 'ADM/0001'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow: New -> Under Review -> (Waitlisted) -> Approved / Rejected
    # ------------------------------------------------------------------
    def action_review(self):
        self.write({'state': 'review', 'reviewer_id': self.env.user.id})

    def action_waitlist(self):
        self.write({
            'state': 'waitlist',
            'reviewer_id': self.env.user.id,
            'decision_date': fields.Date.context_today(self),
        })

    def action_reset(self):
        self.write({'state': 'new', 'decision_date': False, 'rejection_reason': False})

    def action_approve(self):
        Student = self.env['school.student']
        Parent = self.env['school.parent']
        for admission in self:
            if admission.state == 'approved':
                continue
            if not admission.student_id:
                # Re-use an existing record of the same child instead of creating a duplicate.
                student = Student.search([
                    ('name', '=ilike', admission.student_name.strip()),
                    ('date_of_birth', '=', admission.date_of_birth),
                ], limit=1)
                if not student:
                    parent = Parent.search([('email', '=', admission.guardian_email)], limit=1)
                    if not parent:
                        parent = Parent.create({
                            'name': admission.guardian_name,
                            'email': admission.guardian_email,
                            'phone': admission.guardian_phone,
                        })
                    student = Student.create({
                        'name': admission.student_name,
                        'date_of_birth': admission.date_of_birth,
                        'gender': admission.gender,
                        'grade_id': admission.grade_id.id,
                        'academic_year_id': admission.academic_year_id.id,
                        'email': admission.guardian_email,
                        'phone': admission.guardian_phone,
                        'street': admission.address,
                        'parent_ids': [(6, 0, [parent.id])],
                        'primary_parent_id': parent.id,
                        'state': 'enrolled',
                    })
                admission.student_id = student
            admission.write({
                'state': 'approved',
                'reviewer_id': self.env.user.id,
                'decision_date': fields.Date.context_today(self),
            })

    def action_reject(self):
        self.write({
            'state': 'rejected',
            'reviewer_id': self.env.user.id,
            'decision_date': fields.Date.context_today(self),
        })

    def action_open_student(self):
        self.ensure_one()
        if not self.student_id:
            raise UserError(_("No student has been created from this application yet."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'school.student',
            'res_id': self.student_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
