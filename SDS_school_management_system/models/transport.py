from odoo import models, fields, api

class TransportVehicle(models.Model):
    _name = 'school.transport.vehicle'
    _description = 'Transport Vehicle / Bus'

    name = fields.Char(string='Vehicle Registration / Plate No', required=True)
    model_name = fields.Char(string='Vehicle Model')
    driver_name = fields.Char(string='Driver Name', required=True)
    driver_phone = fields.Char(string='Driver Contact No')
    capacity = fields.Integer(string='Seating Capacity', default=40)
    route_ids = fields.One2many('school.transport.route', 'vehicle_id', string='Assigned Routes')


class TransportRoute(models.Model):
    _name = 'school.transport.route'
    _description = 'Transport Route'

    name = fields.Char(string='Route Name', required=True) # e.g. Route A - North City
    code = fields.Char(string='Route Code', required=True)
    vehicle_id = fields.Many2one('school.transport.vehicle', string='Assigned Vehicle')
    fare = fields.Float(string='Monthly Transport Fare', required=True, default=0.0)
    pickup_points = fields.Text(string='Pickup & Drop Points')
    student_registration_ids = fields.One2many('school.transport.registration', 'route_id', string='Subscribed Students')


class TransportRegistration(models.Model):
    _name = 'school.transport.registration'
    _description = 'Student Transport Subscription'

    student_id = fields.Many2one('school.student', string='Student', required=True)
    route_id = fields.Many2one('school.transport.route', string='Transport Route', required=True)
    pickup_point = fields.Char(string='Pickup Point')
    monthly_fare = fields.Float(related='route_id.fare', string='Monthly Fare', store=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='active')
