from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SchoolNotice(models.Model):
    _name = 'school.notice'
    _description = 'School Notice'
    _order = 'pinned desc, date_publish desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Title', required=True, tracking=True)
    body = fields.Html(string='Message', sanitize=True)
    audience = fields.Selection([
        ('all', 'Everyone'),
        ('parents', 'Parents & Guardians'),
        ('staff', 'Teachers & Staff'),
    ], string='Audience', default='all', required=True)
    priority = fields.Selection([
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', required=True)
    pinned = fields.Boolean(string='Pinned', help="Pinned notices stay at the top of the notice board.")
    date_publish = fields.Date(string='Publish Date', default=fields.Date.context_today, required=True)
    date_expiry = fields.Date(string='Expiry Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', required=True, tracking=True)
    author_id = fields.Many2one('res.users', string='Author', default=lambda self: self.env.user, readonly=True)
    is_visible = fields.Boolean(string='Visible Now', compute='_compute_is_visible', search='_search_is_visible')

    @api.constrains('date_publish', 'date_expiry')
    def _check_dates(self):
        for rec in self:
            if rec.date_expiry and rec.date_expiry < rec.date_publish:
                raise ValidationError(_("The expiry date cannot be before the publish date."))

    @api.depends('state', 'date_publish', 'date_expiry')
    def _compute_is_visible(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_visible = bool(
                rec.state == 'published' and rec.date_publish <= today
                and (not rec.date_expiry or rec.date_expiry >= today)
            )

    def _search_is_visible(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise ValidationError(_("Unsupported search on the Visible Now field."))
        today = fields.Date.context_today(self)
        visible = [
            '&', '&',
            ('state', '=', 'published'),
            ('date_publish', '<=', today),
            '|', ('date_expiry', '=', False), ('date_expiry', '>=', today),
        ]
        if (operator == '=') == value:
            return visible
        return ['!'] + visible

    def action_publish(self):
        self.write({'state': 'published'})

    def action_archive_notice(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
