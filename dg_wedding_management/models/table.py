import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class WeddingPhysicalTable(models.Model):
    _name = 'dg.wedding.table'
    _description = 'Physical Hall Table'
    _order = 'hall_id, name'

    name = fields.Char(string="Table No. / Name", required=True)
    hall_id = fields.Many2one('dg.wedding.hall', string="Hall", required=True, ondelete='cascade')
    active = fields.Boolean(default=True)

    shape = fields.Selection([
        ('round', 'Round'),
        ('rectangular', 'Rectangular'),
        ('oval', 'Oval'),
        ('square', 'Square'),
    ], string="Shape", default='round')

    guest_capacity = fields.Integer(string="Standard Capacity (seats)", default=8)
    position_x = fields.Integer(string="Floor Plan X", default=0,
                                help="X position on the visual floor plan (0-100)")
    position_y = fields.Integer(string="Floor Plan Y", default=0,
                                help="Y position on the visual floor plan (0-100)")
    notes = fields.Char(string="Notes")

    @api.constrains('guest_capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.guest_capacity < 1:
                raise ValidationError(_("Table capacity must be at least 1."))


class WeddingTableAssignment(models.Model):
    _name = 'dg.wedding.table.assignment'
    _description = 'Table Assignment for Wedding Event'
    _order = 'table_id'

    wedding_id = fields.Many2one(
        'dg.wedding', string="Wedding Event", ondelete='cascade', required=True
    )
    table_id = fields.Many2one(
        'dg.wedding.table', string="Table", required=True,
        domain="[('hall_id', '=', parent.hall_id)]"
    )
    table_shape = fields.Selection(related='table_id.shape', string="Shape", readonly=True)
    standard_capacity = fields.Integer(
        related='table_id.guest_capacity', string="Standard Capacity", readonly=True
    )

    actual_guests = fields.Integer(string="Guests Seated", default=0)
    assigned_waiter_id = fields.Many2one(
        'dg.wedding.employee',
        string="Assigned Waiter",
        domain="[('employee_type', '=', 'waiter')]",
    )
    menu_id = fields.Many2one(
        'dg.wedding.menu',
        related='wedding_id.wedding_menu_id',
        string="Menu",
        readonly=True,
    )

    # Visual / UX
    is_vip = fields.Boolean(string="VIP Table", default=False)
    special_notes = fields.Char(string="Special Notes")

    # Stats
    occupancy_pct = fields.Float(
        string="Occupancy %", compute='_compute_occupancy', store=True
    )

    @api.depends('actual_guests', 'standard_capacity')
    def _compute_occupancy(self):
        for rec in self:
            if rec.standard_capacity:
                rec.occupancy_pct = (rec.actual_guests / rec.standard_capacity) * 100
            else:
                rec.occupancy_pct = 0.0

    @api.constrains('actual_guests', 'standard_capacity')
    def _check_guests(self):
        for rec in self:
            if rec.actual_guests < 0:
                raise ValidationError(_("Guests seated cannot be negative."))
            if rec.actual_guests > rec.standard_capacity * 1.5:
                raise ValidationError(
                    _("Table '%s' is over 150%% capacity — please adjust guest count.")
                    % rec.table_id.name
                )

    @api.constrains('table_id', 'wedding_id')
    def _check_unique_table(self):
        for rec in self:
            duplicate = self.search([
                ('wedding_id', '=', rec.wedding_id.id),
                ('table_id', '=', rec.table_id.id),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    _("Table '%s' is already assigned to this wedding event.")
                    % rec.table_id.name
                )

    def action_open_assignment_wizard(self):
        """Open the table assignment wizard for quick edits."""
        self.ensure_one()
        _logger.info(
            "Opening table assignment wizard for table %s in wedding %s",
            self.table_id.name, self.wedding_id.name
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Table Assignment — %s") % self.table_id.name,
            'res_model': 'dg.wedding.table.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wedding_id': self.wedding_id.id,
                'default_table_assignment_id': self.id,
                'default_table_id': self.table_id.id,
                'default_actual_guests': self.actual_guests,
                'default_assigned_waiter_id': self.assigned_waiter_id.id,
                'default_is_vip': self.is_vip,
                'default_special_notes': self.special_notes,
            },
        }
