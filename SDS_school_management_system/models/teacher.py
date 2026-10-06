from odoo import models, fields, api

class SchoolTeacher(models.Model):
    _name = 'school.teacher'
    _description = 'Teacher / Faculty'
    _order = 'name'

    name = fields.Char(string='Teacher Name', required=True)
    teacher_id_code = fields.Char(string='Teacher ID', copy=False, readonly=True, default='New')
    qualification = fields.Char(string='Qualification / Degree')
    specialization = fields.Char(string='Specialization Subject')
    date_of_joining = fields.Date(string='Date of Joining', default=fields.Date.today)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', default='male')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    image_1920 = fields.Image(string='Photo')
    subject_ids = fields.Many2many('school.subject', string='Teaches Subjects')
    class_ids = fields.One2many('school.class', 'class_teacher_id', string='Class Teacher of')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('teacher_id_code', 'New') == 'New':
                vals['teacher_id_code'] = self.env['ir.sequence'].next_by_code('school.teacher') or 'TCH/0001'
        return super(SchoolTeacher, self).create(vals_list)
