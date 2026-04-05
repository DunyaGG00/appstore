import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class Wedding(models.Model):
    _name = 'dg.wedding'
    _description = 'Wedding Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'wedding_date desc, id desc'
    _rec_name = 'name'

    # ─── Reference & State ────────────────────────────────────────────────────
    name = fields.Char(
        string="Reference", required=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', tracking=True, index=True)
    color = fields.Integer(string="Color Index", default=0)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Important'), ('2', 'VIP')],
        string="Priority", default='0'
    )

    # ─── Client Information ────────────────────────────────────────────────────
    wedding_owner_name = fields.Char(string="Client Name", required=True, tracking=True)
    wedding_owner_email = fields.Char(string="Email")
    wedding_owner_mobile = fields.Char(string="Mobile", tracking=True)
    wedding_owner_address = fields.Char(string="Address")

    bride_name = fields.Char(string="Bride Name", tracking=True)
    groom_name = fields.Char(string="Groom Name", tracking=True)
    couple_display = fields.Char(
        string="Couple", compute='_compute_couple_display', store=True
    )

    # Contact / Partner link (optional)
    partner_id = fields.Many2one('res.partner', string="Linked Contact")

    # ─── Event Details ─────────────────────────────────────────────────────────
    hall_id = fields.Many2one(
        'dg.wedding.hall', string="Wedding Hall", required=True, tracking=True
    )
    wedding_date = fields.Datetime(string="Event Start", required=True, tracking=True)
    wedding_date_end = fields.Datetime(string="Event End", tracking=True)
    duration_hours = fields.Float(
        string="Duration (hrs)", compute='_compute_duration', store=True
    )
    expected_guests = fields.Integer(string="Expected Guests", tracking=True)
    confirmed_guests = fields.Integer(string="Confirmed Guests")
    theme = fields.Char(string="Wedding Theme / Decor")
    language = fields.Char(string="Ceremony Language")
    ceremony_type = fields.Selection([
        ('civil', 'Civil'),
        ('religious', 'Religious'),
        ('symbolic', 'Symbolic'),
    ], string="Ceremony Type", default='civil')

    # ─── Financials ────────────────────────────────────────────────────────────
    wedding_menu_id = fields.Many2one('dg.wedding.menu', string="Menu Package", tracking=True)
    hall_hire_fee = fields.Float(
        string="Hall Hire Fee", related='hall_id.base_hire_fee',
        readonly=False, store=True, tracking=True
    )
    deposit_amount = fields.Float(string="Deposit Received", tracking=True)
    deposit_date = fields.Date(string="Deposit Date")
    wedding_earnings = fields.Float(string="Total Revenue", tracking=True)
    balance_due = fields.Float(
        string="Balance Due", compute='_compute_financials', store=True
    )

    spending_line_ids = fields.One2many(
        'dg.wedding.spending.line', 'wedding_id', string="Additional Expenses"
    )
    total_cost = fields.Float(
        string="Total Cost", compute='_compute_financials', store=True
    )
    net_profit = fields.Float(
        string="Net Profit", compute='_compute_financials', store=True
    )
    menu_revenue = fields.Float(
        string="Menu Revenue", compute='_compute_financials', store=True
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id
    )

    # ─── Staff & Tables ────────────────────────────────────────────────────────
    employee_line_ids = fields.One2many(
        'dg.wedding.employee.assignment', 'wedding_id', string="Staff"
    )
    table_line_ids = fields.One2many(
        'dg.wedding.table.assignment', 'wedding_id', string="Table Plan"
    )
    total_seated = fields.Integer(
        string="Total Seated Guests", compute='_compute_table_stats', store=True
    )
    tables_assigned = fields.Integer(
        string="Tables Assigned", compute='_compute_table_stats', store=True
    )

    # ─── Notes & Docs ─────────────────────────────────────────────────────────
    wedding_notes = fields.Text(string="Internal Notes")
    contract_number = fields.Char(string="Contract No.")
    contract_signed = fields.Boolean(string="Contract Signed", tracking=True)
    contract_date = fields.Date(string="Contract Date")

    # ─── Computed helpers ─────────────────────────────────────────────────────
    @api.depends('bride_name', 'groom_name')
    def _compute_couple_display(self):
        for rec in self:
            parts = [p for p in [rec.groom_name, rec.bride_name] if p]
            rec.couple_display = ' & '.join(parts) if parts else rec.wedding_owner_name or ''

    @api.depends('wedding_date', 'wedding_date_end')
    def _compute_duration(self):
        for rec in self:
            if rec.wedding_date and rec.wedding_date_end:
                delta = rec.wedding_date_end - rec.wedding_date
                rec.duration_hours = delta.total_seconds() / 3600
            else:
                rec.duration_hours = 0.0

    @api.depends(
        'spending_line_ids.amount',
        'employee_line_ids.total_to_pay',
        'wedding_earnings',
        'deposit_amount',
        'wedding_menu_id.menu_sale_price',
        'confirmed_guests',
        'hall_hire_fee',
    )
    def _compute_financials(self):
        for rec in self:
            misc_cost = sum(rec.spending_line_ids.mapped('amount'))
            staff_cost = sum(rec.employee_line_ids.mapped('total_to_pay'))
            rec.menu_revenue = (rec.confirmed_guests or rec.expected_guests or 0) * (
                rec.wedding_menu_id.menu_sale_price if rec.wedding_menu_id else 0.0
            )
            rec.total_cost = misc_cost + staff_cost + rec.hall_hire_fee
            rec.net_profit = rec.wedding_earnings - rec.total_cost
            rec.balance_due = rec.wedding_earnings - rec.deposit_amount
            _logger.debug(
                "Wedding '%s' financials — revenue: %.2f, cost: %.2f, profit: %.2f",
                rec.name, rec.wedding_earnings, rec.total_cost, rec.net_profit
            )

    @api.depends('table_line_ids.actual_guests')
    def _compute_table_stats(self):
        for rec in self:
            rec.tables_assigned = len(rec.table_line_ids)
            rec.total_seated = sum(rec.table_line_ids.mapped('actual_guests'))

    # ─── Sequence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dg.wedding') or _('New')
        records = super().create(vals_list)
        for rec in records:
            _logger.info(
                "New wedding created: %s | Client: %s | Date: %s",
                rec.name, rec.wedding_owner_name, rec.wedding_date
            )
        return records

    # ─── Constraints ──────────────────────────────────────────────────────────
    @api.constrains('wedding_date', 'wedding_date_end')
    def _check_dates(self):
        for rec in self:
            if rec.wedding_date and rec.wedding_date_end:
                if rec.wedding_date_end <= rec.wedding_date:
                    raise ValidationError(
                        _("Event end date must be after the start date.")
                    )

    @api.constrains('wedding_date', 'hall_id')
    def _check_hall_availability(self):
        for rec in self:
            if not rec.hall_id or not rec.wedding_date:
                continue
            domain = [
                ('hall_id', '=', rec.hall_id.id),
                ('state', 'not in', ['cancel', 'draft']),
                ('id', '!=', rec.id),
            ]
            if rec.wedding_date_end:
                domain += [
                    ('wedding_date', '<', rec.wedding_date_end),
                    ('wedding_date_end', '>', rec.wedding_date),
                ]
            else:
                domain += [
                    ('wedding_date', '=', rec.wedding_date),
                ]
            conflict = self.search(domain, limit=1)
            if conflict:
                raise ValidationError(
                    _("Hall '%s' is already booked for '%s' during this time period.")
                    % (rec.hall_id.name, conflict.name)
                )

    @api.constrains('wedding_earnings', 'deposit_amount')
    def _check_financials(self):
        for rec in self:
            if rec.wedding_earnings < 0:
                raise ValidationError(_("Total revenue cannot be negative."))
            if rec.deposit_amount < 0:
                raise ValidationError(_("Deposit amount cannot be negative."))

    # ─── State Transitions ────────────────────────────────────────────────────
    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only quotations can be confirmed."))
            rec.state = 'confirmed'
            _logger.info("Wedding confirmed: %s", rec.name)
            rec.message_post(
                body=_("Wedding confirmed. Client: %s | Hall: %s | Date: %s")
                % (rec.wedding_owner_name, rec.hall_id.name, rec.wedding_date)
            )

    def action_start(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_("Only confirmed weddings can be started."))
            rec.state = 'in_progress'
            _logger.info("Wedding started: %s", rec.name)
            rec.message_post(body=_("Event is now in progress."))

    def action_done(self):
        for rec in self:
            if rec.state not in ('confirmed', 'in_progress'):
                raise UserError(_("Cannot complete a wedding that is not confirmed or in progress."))
            rec.state = 'done'
            _logger.info("Wedding completed: %s — net profit: %.2f", rec.name, rec.net_profit)
            rec.message_post(
                body=_("Event completed. Revenue: %.2f | Cost: %.2f | Profit: %.2f")
                % (rec.wedding_earnings, rec.total_cost, rec.net_profit)
            )

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_("Cannot cancel a completed wedding."))
            rec.state = 'cancel'
            _logger.warning("Wedding cancelled: %s", rec.name)
            rec.message_post(body=_("Wedding event has been cancelled."))

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancel':
                raise UserError(_("Only cancelled weddings can be reset to draft."))
            rec.state = 'draft'
            _logger.info("Wedding reset to draft: %s", rec.name)

    # ─── Report Actions ───────────────────────────────────────────────────────
    def action_print_wedding_report(self):
        return self.env.ref(
            'dg_wedding_management.action_report_wedding_summary'
        ).report_action(self)

    def action_open_report_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Generate Report"),
            'res_model': 'dg.wedding.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_wedding_id': self.id},
        }

    # ─── Table Floor Plan ─────────────────────────────────────────────────────
    def action_open_floor_plan(self):
        """Open the interactive HTML floor plan for this wedding's hall."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/dg_wedding_management/floor_plan/%d' % self.id,
            'target': 'new',
        }


class WeddingSpendingLine(models.Model):
    _name = 'dg.wedding.spending.line'
    _description = 'Wedding Additional Expense'
    _order = 'date desc'

    wedding_id = fields.Many2one(
        'dg.wedding', string="Wedding Event", ondelete='cascade', required=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='wedding_id.currency_id', store=False, readonly=True
    )
    name = fields.Char(string="Description", required=True)
    category = fields.Selection([
        ('catering', 'Catering / Extras'),
        ('decoration', 'Decoration'),
        ('entertainment', 'Entertainment'),
        ('transport', 'Transport'),
        ('photography', 'Photography / Video'),
        ('other', 'Other'),
    ], string="Category", default='other')
    amount = fields.Float(string="Amount", required=True)
    date = fields.Date(string="Date", default=fields.Date.context_today)
    paid = fields.Boolean(string="Paid", default=False)
    notes = fields.Char(string="Notes")

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Expense amount cannot be negative."))
