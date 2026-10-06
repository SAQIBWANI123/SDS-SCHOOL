from odoo import models, fields, api

class SchoolGrade(models.Model):
    _name = 'school.grade'
    _description = 'Grade / Standard'
    _order = 'sequence, name'

    name = fields.Char(string='Grade Name', required=True) # e.g. Grade 10, Kindergarten
    code = fields.Char(string='Grade Code', required=True, readonly=True, copy=False, default='New')
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    subject_ids = fields.Many2many('school.subject', string='Curriculum Subjects')
    class_ids = fields.One2many('school.class', 'grade_id', string='Classes / Sections')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('school.grade') or 'GRD/0001'
        return super(SchoolGrade, self).create(vals_list)
