import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SmartImportConfig(models.Model):
    """
    Per-model Smart Import configuration.

    When a record is saved with `enabled=True`, a server action is automatically
    created and bound to that model's list and form views. The action opens the
    Smart Import wizard. Disabling or deleting the config tears down the action.
    """
    _name = 'dg.smart.import.config'
    _description = 'Smart Import Configuration'
    _rec_name = 'model_id'
    _order = 'model_id'

    model_id = fields.Many2one(
        'ir.model',
        string="Model",
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
    )
    model_name = fields.Char(
        related='model_id.model',
        store=True,
        string="Technical Name",
        readonly=True,
    )
    enabled = fields.Boolean(string="Enable Smart Import", default=False)
    server_action_id = fields.Many2one(
        'ir.actions.server',
        string="Bound Server Action",
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    _sql_constraints = [
        ('unique_model', 'unique(model_id)',
         'A Smart Import configuration already exists for this model.'),
    ]

    # ── Server Action Lifecycle ────────────────────────────────────────────────

    def _get_group(self):
        return self.env.ref('dg_smart_import.group_smart_import_manager')

    def _build_action_vals(self):
        """Return create-vals for the Smart Import server action."""
        self.ensure_one()
        return {
            'name': _("Smart Import"),
            'model_id': self.model_id.id,
            'binding_model_id': self.model_id.id,
            # 'list,form' makes it appear in both the list-view Actions menu
            # (⚙ gear, visible after selecting ≥1 record) and the form-view
            # Actions menu.  'binding_type' must be 'action' (the default) so
            # it is not restricted to form-only.
            'binding_view_types': 'list,form',
            'binding_type': 'action',
            'state': 'code',
            'code': (
                "action = env['dg.smart.import.wizard']"
                ".action_open_wizard(model._name)"
            ),
            'groups_id': [(4, self._get_group().id)],
        }

    def _create_server_action(self):
        self.ensure_one()
        action = self.env['ir.actions.server'].create(self._build_action_vals())
        # Use super().write to avoid triggering our own write override
        super(SmartImportConfig, self).write({'server_action_id': action.id})
        # Invalidate the action-bindings cache so the button appears immediately
        # in the list/form view without requiring a server restart.
        self.env['ir.actions.server'].clear_caches()
        _logger.info(
            "Smart Import: server action #%d created for model '%s'",
            action.id, self.model_name,
        )

    def _remove_server_action(self):
        self.ensure_one()
        if self.server_action_id:
            action = self.server_action_id
            super(SmartImportConfig, self).write({'server_action_id': False})
            action.unlink()
            self.env['ir.actions.server'].clear_caches()
            _logger.info(
                "Smart Import: server action removed for model '%s'",
                self.model_name,
            )

    # ── ORM Overrides ──────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.enabled:
                rec._create_server_action()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'enabled' in vals or 'model_id' in vals:
            for rec in self:
                if rec.enabled and not rec.server_action_id:
                    rec._create_server_action()
                elif not rec.enabled and rec.server_action_id:
                    rec._remove_server_action()
        return result

    def unlink(self):
        for rec in self:
            rec._remove_server_action()
        return super().unlink()

    # ── Manual Toggle ──────────────────────────────────────────────────────────

    def action_toggle_enabled(self):
        """Button action: flip the enabled flag."""
        for rec in self:
            rec.enabled = not rec.enabled
