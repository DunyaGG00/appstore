import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WeddingReportWizard(models.TransientModel):
    """
    Wizard to select which type of PDF report to generate
    for a wedding event.
    """
    _name = 'dg.wedding.report.wizard'
    _description = 'Wedding Report Wizard'

    wedding_id = fields.Many2one(
        'dg.wedding', string="Wedding Event", required=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    report_type = fields.Selection([
        ('summary', 'Full Event Summary'),
        ('staff', 'Staff & Payroll Report'),
        ('financial', 'Financial Report'),
        ('table_plan', 'Table Plan Report'),
    ], string="Report Type", required=True, default='summary')

    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    notes = fields.Text(string="Additional Notes for Report")

    def action_generate_report(self):
        self.ensure_one()
        _logger.info(
            "Generating report type '%s' for wedding: %s",
            self.report_type, self.wedding_id.name
        )

        report_map = {
            'summary': 'dg_wedding_management.action_report_wedding_summary',
            'staff': 'dg_wedding_management.action_report_wedding_staff',
            'financial': 'dg_wedding_management.action_report_wedding_financial',
            'table_plan': 'dg_wedding_management.action_report_wedding_table_plan',
        }
        ref = report_map.get(self.report_type)
        if not ref:
            raise UserError(_("Unknown report type."))

        return self.env.ref(ref).report_action(self.wedding_id)
