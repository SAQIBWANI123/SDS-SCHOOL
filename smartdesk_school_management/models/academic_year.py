from odoo import models, fields, api

class AcademicYear(models.Model):
    _name = 'school.academic.year'
    _description = 'Academic Year'
    _order = 'date_start desc'

    name = fields.Char(string='Academic Year', required=True)
    code = fields.Char(string='Code', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    active = fields.Boolean(string='Active', default=True)
    current = fields.Boolean(string='Current Academic Year', default=False)
    term_ids = fields.One2many('school.academic.term', 'academic_year_id', string='Terms')
    description = fields.Text(string='Description')

    @api.onchange('current')
    def _onchange_current(self):
        if self.current:
            other_years = self.search([('id', '!=', self._origin.id)])
            other_years.write({'current': False})


class AcademicTerm(models.Model):
    _name = 'school.academic.term'
    _description = 'Academic Term'
    _order = 'date_start asc'

    name = fields.Char(string='Term Name', required=True)
    code = fields.Char(string='Code', required=True)
    academic_year_id = fields.Many2one('school.academic.year', string='Academic Year', required=True, ondelete='cascade')
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    active = fields.Boolean(string='Active', default=True)
