from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

LOAN_DAYS = 14
RENEW_DAYS = 7
MAX_RENEWALS = 2
OUT_STATES = ('issued', 'overdue')


class LibraryBook(models.Model):
    _name = 'school.library.book'
    _description = 'Library Book Catalog'

    name = fields.Char(string='Book Title', required=True)
    code = fields.Char(string='Book Code / Call No', readonly=True, copy=False, default='New')
    isbn = fields.Char(string='ISBN No')
    author = fields.Char(string='Author(s)', required=True)
    publisher = fields.Char(string='Publisher')
    edition = fields.Char(string='Edition / Year')
    category = fields.Selection([
        ('textbook', 'Textbook'),
        ('reference', 'Reference Book'),
        ('fiction', 'Fiction'),
        ('nonfiction', 'Non-Fiction'),
        ('journal', 'Journal / Magazine'),
    ], string='Category', default='textbook', required=True)
    total_copies = fields.Integer(string='Total Copies', default=1, required=True)
    available_copies = fields.Integer(string='Available Copies', compute='_compute_available_copies', store=True)
    issue_ids = fields.One2many('school.library.issue', 'book_id', string='Issue Records')

    @api.constrains('total_copies')
    def _check_total_copies(self):
        for rec in self:
            if rec.total_copies < 0:
                raise ValidationError(_("Total copies cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('school.library.book') or 'BK/00001'
        return super().create(vals_list)

    @api.depends('total_copies', 'issue_ids.state')
    def _compute_available_copies(self):
        for rec in self:
            out = len(rec.issue_ids.filtered(lambda i: i.state in OUT_STATES))
            rec.available_copies = max(rec.total_copies - out, 0)


class LibraryIssue(models.Model):
    _name = 'school.library.issue'
    _description = 'Library Book Issue Record'
    _order = 'date_issue desc, id desc'

    name = fields.Char(string='Issue Ref', readonly=True, copy=False, default='New')
    book_id = fields.Many2one('school.library.book', string='Book Title', required=True)
    student_id = fields.Many2one('school.student', string='Student', required=True)
    class_id = fields.Many2one('school.class', related='student_id.class_id', string='Class / Section', store=True)
    date_issue = fields.Date(string='Issue Date', default=fields.Date.context_today, required=True)
    date_due = fields.Date(
        string='Due Date', required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=LOAN_DAYS))
    date_return = fields.Date(string='Return Date')
    renew_count = fields.Integer(string='Renewals', default=0, copy=False)
    days_overdue = fields.Integer(string='Days Overdue', compute='_compute_days_overdue')

    state = fields.Selection([
        ('issued', 'Issued'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ], string='Status', default='issued', required=True)

    fine_amount = fields.Float(string='Late Fine Amount', default=0.0)

    @api.constrains('date_issue', 'date_due')
    def _check_dates(self):
        for rec in self:
            if rec.date_due and rec.date_issue and rec.date_due < rec.date_issue:
                raise ValidationError(_("The due date cannot be earlier than the issue date."))

    @api.depends('state', 'date_due', 'date_return')
    def _compute_days_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            end = rec.date_return if rec.state == 'returned' and rec.date_return else today
            rec.days_overdue = max((end - rec.date_due).days, 0) if rec.date_due else 0

    @api.model
    def _fine_per_day(self):
        value = self.env['ir.config_parameter'].sudo().get_param('school.library_fine_per_day', '1.0')
        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            return 1.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('school.library.issue') or 'ISS/0001'
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: r.state in OUT_STATES):
            book = rec.book_id
            if len(book.issue_ids.filtered(lambda i: i.state in OUT_STATES)) > book.total_copies:
                raise UserError(_("No copy of '%s' is currently available.", book.name))
        return records

    def action_return_book(self):
        today = fields.Date.context_today(self)
        rate = self._fine_per_day()
        for rec in self:
            if rec.state == 'returned':
                continue
            late_days = max((today - rec.date_due).days, 0)
            rec.write({
                'date_return': today,
                'state': 'returned',
                'fine_amount': late_days * rate,
            })

    def action_renew(self):
        for rec in self:
            if rec.state == 'returned':
                raise UserError(_("A returned book cannot be renewed."))
            if rec.renew_count >= MAX_RENEWALS:
                raise UserError(_("%(ref)s has already been renewed %(count)s times.",
                                  ref=rec.name, count=MAX_RENEWALS))
            rec.write({
                'date_due': rec.date_due + timedelta(days=RENEW_DAYS),
                'renew_count': rec.renew_count + 1,
                'state': 'issued',
                'fine_amount': 0.0,
            })

    @api.model
    def _cron_flag_overdue(self):
        """Daily job: mark late loans as overdue and keep the running fine up to date."""
        today = fields.Date.context_today(self)
        rate = self._fine_per_day()
        late = self.search([
            ('state', 'in', OUT_STATES), ('date_due', '<', today),
        ])
        for rec in late:
            rec.write({
                'state': 'overdue',
                'fine_amount': (today - rec.date_due).days * rate,
            })
        return True
