from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import html2plaintext


class SchoolDashboard(models.AbstractModel):
    _name = 'school.dashboard'
    _description = 'CampusPulse Dashboard Data Provider'

    @api.model
    def get_dashboard_data(self):
        """Single RPC feeding the whole dashboard. Every block degrades gracefully
        when the current user lacks access to the underlying model."""
        today = fields.Date.context_today(self)
        company = self.env.company
        year = self.env['school.academic.year'].search([('current', '=', True)], limit=1)
        data = {
            'user_name': self.env.user.name,
            'company': company.name,
            'today': fields.Date.to_string(today),
            'academic_year': year.name if year else False,
            'currency': {
                'symbol': company.currency_id.symbol or '',
                'position': company.currency_id.position or 'before',
            },
        }
        blocks = [
            ('kpis', self._block_kpis, {}),
            ('grades', self._block_grades, []),
            ('gender', self._block_gender, {'male': 0, 'female': 0, 'other': 0}),
            ('attendance_week', self._block_attendance_week, []),
            ('fee_months', self._block_fee_months, []),
            ('fee_states', self._block_fee_states, []),
            ('overdue_fees', self._block_overdue_fees, []),
            ('admissions', self._block_admissions, []),
            ('notices', self._block_notices, []),
            ('exams', self._block_exams, []),
            ('birthdays', self._block_birthdays, []),
            ('classes', self._block_classes, []),
        ]
        for key, method, default in blocks:
            try:
                data[key] = method(today)
            except AccessError:
                data[key] = default
        return data

    @staticmethod
    def _short_class(klass):
        if not klass:
            return ''
        return ' - '.join(x for x in (klass.grade_id.name, klass.section) if x)

    # ------------------------------------------------------------------
    def _block_kpis(self, today):
        env = self.env
        Student = env['school.student']
        kpis = {
            'students': Student.search_count([]),
            'enrolled': Student.search_count([('state', '=', 'enrolled')]),
            'teachers': env['school.teacher'].search_count([]),
            'classes': env['school.class'].search_count([]),
            'pending_admissions': env['school.admission'].search_count([('state', 'in', ('new', 'review'))]),
            'waitlisted': env['school.admission'].search_count([('state', '=', 'waitlist')]),
            'books': env['school.library.book'].search_count([]),
        }
        lines = env['school.attendance.line']._read_group(
            [('date', '=', today), ('attendance_id.state', '=', 'done')], ['state'], ['__count'])
        total = sum(c for _s, c in lines)
        present = sum(c for s, c in lines if s in ('present', 'late', 'excused'))
        kpis.update({
            'att_total': total,
            'att_present': present,
            'att_pct': round(present * 100.0 / total, 1) if total else None,
        })
        Fee = env['school.student.fee']
        billed, paid, due = Fee._read_group(
            [('state', 'in', ('posted', 'partially_paid', 'paid'))], [],
            ['amount_total:sum', 'amount_paid:sum', 'amount_due:sum'])[0]
        o_count, o_due = Fee._read_group([('is_overdue', '=', True)], [], ['__count', 'amount_due:sum'])[0]
        kpis.update({
            'fee_billed': billed or 0.0, 'fee_paid': paid or 0.0, 'fee_due': due or 0.0,
            'fee_pct': round((paid or 0.0) * 100.0 / billed, 1) if billed else 0.0,
            'overdue_count': o_count, 'overdue_amount': o_due or 0.0,
        })
        kpis['library_out'] = env['school.library.issue'].search_count([('state', 'in', ('issued', 'overdue'))])
        kpis['library_late'] = env['school.library.issue'].search_count([
            '|', ('state', '=', 'overdue'), '&', ('state', '=', 'issued'), ('date_due', '<', today)])
        return kpis

    def _block_grades(self, today):
        rows = self.env['school.student']._read_group(
            [('state', '=', 'enrolled')], ['grade_id'], ['__count'])
        rows = sorted(((g, c) for g, c in rows if g), key=lambda r: (r[0].sequence, r[0].name))
        return [{'id': g.id, 'name': g.name, 'count': c} for g, c in rows]

    def _block_gender(self, today):
        res = {'male': 0, 'female': 0, 'other': 0}
        for gender, count in self.env['school.student']._read_group(
                [('state', '=', 'enrolled')], ['gender'], ['__count']):
            res[gender or 'other'] = count
        return res

    def _block_attendance_week(self, today):
        start = today - timedelta(days=6)
        rows = self.env['school.attendance.line']._read_group(
            [('date', '>=', start), ('date', '<=', today), ('attendance_id.state', '=', 'done')],
            ['date:day', 'state'], ['__count'])
        per_day = {}
        for day, state, count in rows:
            key = fields.Date.to_date(day)
            tot = per_day.setdefault(key, [0, 0])
            tot[1] += count
            if state in ('present', 'late', 'excused'):
                tot[0] += count
        out = []
        for i in range(7):
            d = start + timedelta(days=i)
            present, total = per_day.get(d, (0, 0))
            out.append({
                'label': d.strftime('%a'), 'date': fields.Date.to_string(d),
                'present': present, 'total': total,
                'pct': round(present * 100.0 / total) if total else None,
            })
        return out

    def _block_fee_months(self, today):
        first = today.replace(day=1) - relativedelta(months=5)
        months = [first + relativedelta(months=i) for i in range(6)]
        billed, collected = {}, {}
        for day, amount in self.env['school.student.fee']._read_group(
                [('date_invoice', '>=', first), ('state', 'in', ('posted', 'partially_paid', 'paid'))],
                ['date_invoice:month'], ['amount_total:sum']):
            billed[(day.year, day.month)] = amount
        for day, amount in self.env['school.fee.payment']._read_group(
                [('date', '>=', first)], ['date:month'], ['amount:sum']):
            collected[(day.year, day.month)] = amount
        return [{
            'label': m.strftime('%b'),
            'billed': billed.get((m.year, m.month), 0.0),
            'collected': collected.get((m.year, m.month), 0.0),
        } for m in months]

    def _block_fee_states(self, today):
        Fee = self.env['school.student.fee']
        labels = dict(Fee.fields_get(['state'])['state']['selection'])
        rows = Fee._read_group([('state', '!=', 'cancelled')], ['state'], ['__count', 'amount_total:sum'])
        total = sum(a or 0.0 for _s, _c, a in rows)
        return [{
            'state': s, 'label': labels.get(s, s), 'count': c, 'amount': a or 0.0,
            'pct': round((a or 0.0) * 100.0 / total) if total else 0,
        } for s, c, a in rows]

    def _block_overdue_fees(self, today):
        fees = self.env['school.student.fee'].search([('is_overdue', '=', True)], order='date_due asc', limit=5)
        return [{
            'id': f.id, 'name': f.name, 'student': f.student_id.name,
            'class': self._short_class(f.class_id), 'due': f.amount_due, 'days': f.days_overdue,
        } for f in fees]

    def _block_admissions(self, today):
        Adm = self.env['school.admission']
        labels = dict(Adm.fields_get(['state'])['state']['selection'])
        return [{
            'id': a.id, 'name': a.name, 'student_name': a.student_name,
            'grade': a.grade_id.name or '', 'state': a.state, 'state_label': labels.get(a.state, a.state),
            'date': fields.Date.to_string(a.create_date.date()) if a.create_date else '',
        } for a in Adm.search([], order='create_date desc, id desc', limit=6)]

    def _block_notices(self, today):
        notices = self.env['school.notice'].search([('is_visible', '=', True)], limit=5)
        out = []
        for n in notices:
            text = html2plaintext(n.body or '').strip()
            out.append({
                'id': n.id, 'title': n.name, 'priority': n.priority, 'pinned': n.pinned,
                'date': fields.Date.to_string(n.date_publish),
                'excerpt': (text[:110] + '…') if len(text) > 110 else text,
            })
        return out

    def _block_exams(self, today):
        exams = self.env['school.exam'].search(
            [('date_end', '>=', today), ('state', '!=', 'completed')], order='date_start asc', limit=4)
        return [{
            'id': e.id, 'name': e.name, 'grade': e.grade_id.name,
            'start': fields.Date.to_string(e.date_start), 'end': fields.Date.to_string(e.date_end),
            'state': e.state, 'days': (e.date_start - today).days,
        } for e in exams]

    def _block_birthdays(self, today):
        people = []
        for model, role in (('school.student', 'Student'), ('school.teacher', 'Teacher')):
            domain = [('state', '=', 'enrolled')] if model == 'school.student' else []
            fname = 'date_of_birth' if model == 'school.student' else None
            if not fname:
                continue
            for rec in self.env[model].search(domain + [(fname, '!=', False)]):
                dob = rec[fname]
                try:
                    nxt = dob.replace(year=today.year)
                except ValueError:  # 29 Feb
                    nxt = date(today.year, 2, 28)
                if nxt < today:
                    nxt = nxt.replace(year=today.year + 1) if not (dob.month == 2 and dob.day == 29) else date(today.year + 1, 2, 28)
                delta = (nxt - today).days
                if delta <= 7:
                    people.append({'name': rec.name, 'role': role, 'days': delta,
                                   'label': nxt.strftime('%d %b'), 'age': nxt.year - dob.year})
        return sorted(people, key=lambda p: p['days'])[:6]

    def _block_classes(self, today):
        classes = self.env['school.class'].search([], order='student_count desc, id', limit=6)
        return [{'id': c.id, 'name': self._short_class(c), 'count': c.student_count,
                 'capacity': c.capacity or 0} for c in classes]
