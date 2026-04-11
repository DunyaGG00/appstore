import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class WeddingEmployee(models.Model):
    _name = 'dg.wedding.employee'
    _description = 'Wedding Employee'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string="Full Name", required=True, tracking=True)
    image = fields.Image(string="Photo", max_width=256, max_height=256)
    active = fields.Boolean(default=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    phone = fields.Char(string="Phone", tracking=True)
    email = fields.Char(string="Email")
    id_number = fields.Char(string="ID / Passport No.")
    address = fields.Text(string="Address")

    employee_type = fields.Selection([
        ('waiter', 'Waiter'),
        ('chef', 'Chef'),
        ('security', 'Security'),
        ('manager', 'Manager'),
        ('cleaner', 'Cleaner'),
        ('entertainment', 'Entertainment'),
        ('coordinator', 'Coordinator'),
        ('photographer', 'Photographer'),
    ], string="Role", required=True, tracking=True)

    payment_type = fields.Selection([
        ('monthly', 'Monthly Salary'),
        ('per_wedding', 'Per Event (Fixed Fee)'),
    ], string="Payment Type", default='per_wedding', required=True, tracking=True)

    monthly_wage = fields.Float(string="Monthly Salary", tracking=True)
    event_fee = fields.Float(
        string="Event Fee",
        tracking=True,
        help="Fixed payment per event — does not depend on hours worked.",
    )

    notes = fields.Text(string="Internal Notes")

    assignment_ids = fields.One2many(
        'dg.wedding.employee.assignment', 'employee_id', string="Assignments"
    )
    assignment_count = fields.Integer(
        string="Events", compute='_compute_assignment_count'
    )
    total_earned = fields.Float(
        string="Total Earned", compute='_compute_assignment_count'
    )

    @api.depends('assignment_ids', 'assignment_ids.total_to_pay')
    def _compute_assignment_count(self):
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)
            rec.total_earned = sum(rec.assignment_ids.mapped('total_to_pay'))
            _logger.debug(
                "Employee %s — %d assignments, total earned: %.2f",
                rec.name, rec.assignment_count, rec.total_earned
            )

    @api.constrains('monthly_wage', 'event_fee')
    def _check_wages(self):
        for rec in self:
            if rec.payment_type == 'monthly' and rec.monthly_wage < 0:
                raise ValidationError(_("Monthly salary cannot be negative."))
            if rec.payment_type == 'per_wedding' and rec.event_fee < 0:
                raise ValidationError(_("Event fee cannot be negative."))

    @api.model
    def name_create(self, name):
        """Disable quick-create: Role is required and cannot be set inline."""
        raise UserError(
            _("To add a staff member, open Staff from the Configuration menu "
              "and fill in the full form — Role is mandatory.")
        )

    def action_view_assignments(self):
        self.ensure_one()
        _logger.info("Opening assignments for employee: %s", self.name)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Assignments — %s") % self.name,
            'res_model': 'dg.wedding.employee.assignment',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }


class WeddingEmployeeAssignment(models.Model):
    _name = 'dg.wedding.employee.assignment'
    _description = 'Staff Assignment for Wedding Event'
    _order = 'wedding_id desc'

    wedding_id = fields.Many2one(
        'dg.wedding', string="Wedding Event", ondelete='cascade', required=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='wedding_id.currency_id', store=False, readonly=True
    )
    employee_id = fields.Many2one(
        'dg.wedding.employee', string="Employee", required=True
    )
    role = fields.Selection(related='employee_id.employee_type', string="Role", store=True)
    payment_type = fields.Selection(
        related='employee_id.payment_type', string="Payment Type", store=True
    )

    # Informational – does NOT affect payment amount
    hours_worked = fields.Float(
        string="Hours Worked",
        help="Actual hours worked — for record-keeping only, not used in payment calculation.",
    )

    # Fixed fee copied from the employee profile; can be overridden per event
    event_fee = fields.Float(
        string="Event Fee",
        related='employee_id.event_fee',
        readonly=False,
        store=True,
        help="Fixed payment for this event — does not depend on hours worked.",
    )

    total_to_pay = fields.Float(
        string="Total to Pay", compute='_compute_pay', store=True
    )
    notes = fields.Char(string="Notes")

    @api.depends('event_fee', 'payment_type')
    def _compute_pay(self):
        for rec in self:
            if rec.payment_type == 'monthly':
                # Monthly staff cost is tracked separately; per-event entry = 0
                rec.total_to_pay = 0.0
            else:
                # Fixed fee per event regardless of hours worked
                rec.total_to_pay = rec.event_fee
            _logger.debug(
                "Assignment pay computed — employee: %s, pay: %.2f",
                rec.employee_id.name, rec.total_to_pay
            )
