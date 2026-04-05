import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WeddingHall(models.Model):
    _name = 'dg.wedding.hall'
    _description = 'Wedding Hall / Venue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string="Hall Name", required=True, tracking=True)
    code = fields.Char(string="Hall Code", tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    image = fields.Image(string="Hall Photo", max_width=1024, max_height=1024)
    description = fields.Text(string="Description / Notes")

    # Location
    address = fields.Char(string="Address")
    city = fields.Char(string="City")
    country_id = fields.Many2one('res.country', string="Country")

    # Capacity
    physical_table_ids = fields.One2many(
        'dg.wedding.table', 'hall_id', string="Tables"
    )
    total_guest_capacity = fields.Integer(
        string="Total Capacity (seats)", compute='_compute_capacity', store=True
    )
    table_count = fields.Integer(
        string="Number of Tables", compute='_compute_capacity', store=True
    )

    # Financials
    base_hire_fee = fields.Float(string="Base Hire Fee")
    currency_id = fields.Many2one(
        'res.currency', string="Currency",
        default=lambda self: self.env.company.currency_id
    )

    # Stats
    wedding_count = fields.Integer(
        string="Weddings Hosted", compute='_compute_wedding_count'
    )

    @api.depends('physical_table_ids.guest_capacity')
    def _compute_capacity(self):
        for hall in self:
            hall.table_count = len(hall.physical_table_ids)
            hall.total_guest_capacity = sum(
                hall.physical_table_ids.mapped('guest_capacity')
            )
            _logger.debug(
                "Hall '%s' capacity recomputed: %d seats across %d tables",
                hall.name, hall.total_guest_capacity, hall.table_count
            )

    def _compute_wedding_count(self):
        WeddingModel = self.env['dg.wedding']
        for hall in self:
            hall.wedding_count = WeddingModel.search_count([('hall_id', '=', hall.id)])

    @api.constrains('base_hire_fee')
    def _check_hire_fee(self):
        for rec in self:
            if rec.base_hire_fee < 0:
                raise ValidationError(_("Base hire fee cannot be negative."))

    def action_open_hall_plan(self):
        self.ensure_one()
        _logger.info("Opening hall floor plan for: %s", self.name)
        return {
            'type': 'ir.actions.act_url',
            'url': '/dg_wedding_management/hall_plan/%d' % self.id,
            'target': 'new',
        }

    def action_view_weddings(self):
        self.ensure_one()
        _logger.info("Viewing weddings for hall: %s", self.name)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Weddings — %s") % self.name,
            'res_model': 'dg.wedding',
            'view_mode': 'list,form',
            'domain': [('hall_id', '=', self.id)],
            'context': {'default_hall_id': self.id},
        }
