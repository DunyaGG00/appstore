import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WeddingTableAssignmentWizard(models.TransientModel):
    """
    Quick-edit wizard for a single table assignment.
    Lets the user pick a table, set how many guests sit,
    and assign a waiter — all from a compact popup dialog.
    """
    _name = 'dg.wedding.table.assignment.wizard'
    _description = 'Table Assignment Wizard'

    wedding_id = fields.Many2one(
        'dg.wedding', string="Wedding Event", required=True,
        readonly=True,
    )
    table_assignment_id = fields.Many2one(
        'dg.wedding.table.assignment', string="Existing Assignment"
    )
    table_id = fields.Many2one(
        'dg.wedding.table', string="Table", required=True,
        domain="[('hall_id', '=', hall_id)]",
    )
    hall_id = fields.Many2one(
        'dg.wedding.hall', string="Hall",
        related='wedding_id.hall_id', readonly=True,
    )

    # ── Guest info ────────────────────────────────────────────────────────────
    standard_capacity = fields.Integer(
        string="Standard Capacity", related='table_id.guest_capacity', readonly=True
    )
    actual_guests = fields.Integer(string="Guests to Seat", default=0)

    # ── Waiter ────────────────────────────────────────────────────────────────
    assigned_waiter_id = fields.Many2one(
        'dg.wedding.employee',
        string="Assign Waiter",
        domain="[('employee_type', '=', 'waiter')]",
    )
    available_waiter_ids = fields.Many2many(
        'dg.wedding.employee',
        string="Available Waiters",
        compute='_compute_available_waiters',
    )

    # ── Other ─────────────────────────────────────────────────────────────────
    is_vip = fields.Boolean(string="VIP Table")
    special_notes = fields.Char(string="Special Notes")

    @api.depends('wedding_id')
    def _compute_available_waiters(self):
        for wiz in self:
            # Waiters already assigned to THIS wedding's staff
            assigned_waiter_ids = wiz.wedding_id.employee_line_ids.filtered(
                lambda l: l.role == 'waiter'
            ).mapped('employee_id').ids
            if assigned_waiter_ids:
                wiz.available_waiter_ids = [(6, 0, assigned_waiter_ids)]
            else:
                # Fall back to all waiters
                wiz.available_waiter_ids = self.env['dg.wedding.employee'].search(
                    [('employee_type', '=', 'waiter')]
                )

    @api.constrains('actual_guests', 'standard_capacity')
    def _check_guests(self):
        for wiz in self:
            if wiz.actual_guests < 0:
                raise ValidationError(_("Number of guests cannot be negative."))
            if wiz.standard_capacity and wiz.actual_guests > wiz.standard_capacity * 1.5:
                raise ValidationError(
                    _("Table '%s' max seating is 150%% of standard capacity (%d seats).")
                    % (wiz.table_id.name, int(wiz.standard_capacity * 1.5))
                )

    def action_apply(self):
        """Apply the wizard values to the table assignment record."""
        self.ensure_one()
        vals = {
            'actual_guests': self.actual_guests,
            'assigned_waiter_id': self.assigned_waiter_id.id,
            'is_vip': self.is_vip,
            'special_notes': self.special_notes,
        }

        if self.table_assignment_id:
            self.table_assignment_id.write(vals)
            _logger.info(
                "Table assignment updated via wizard — table: %s, guests: %d, waiter: %s",
                self.table_id.name, self.actual_guests,
                self.assigned_waiter_id.name or '—'
            )
        else:
            # Create new assignment
            vals.update({
                'wedding_id': self.wedding_id.id,
                'table_id': self.table_id.id,
            })
            self.env['dg.wedding.table.assignment'].create(vals)
            _logger.info(
                "New table assignment created via wizard — table: %s, wedding: %s",
                self.table_id.name, self.wedding_id.name
            )

        return {'type': 'ir.actions.act_window_close'}

    def action_apply_and_new(self):
        """Apply and open a new wizard for the same wedding."""
        self.action_apply()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Assign Another Table"),
            'res_model': 'dg.wedding.table.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_wedding_id': self.wedding_id.id},
        }
