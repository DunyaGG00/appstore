import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WeddingMenu(models.Model):
    _name = 'dg.wedding.menu'
    _description = 'Wedding Menu Package'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string="Menu Name", required=True, tracking=True)
    active = fields.Boolean(default=True)

    category = fields.Selection([
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('vip', 'VIP / Luxury'),
        ('vegetarian', 'Vegetarian'),
        ('custom', 'Custom'),
    ], string="Category", default='standard', tracking=True)

    description = fields.Text(string="Description")
    serves_count = fields.Integer(
        string="Min. Guests", default=1,
        help="Minimum number of guests this menu is designed for"
    )

    menu_sale_price = fields.Float(
        string="Sale Price (per person)", tracking=True
    )
    menu_cost = fields.Float(
        string="Cost (per person)",
        compute='_compute_menu_cost',
        store=True,
    )
    margin_pct = fields.Float(
        string="Margin %", compute='_compute_margin', store=True
    )

    menu_line_ids = fields.One2many(
        'dg.wedding.menu.line', 'menu_id', string="Menu Items"
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id
    )

    @api.depends('menu_line_ids.subtotal_cost')
    def _compute_menu_cost(self):
        for menu in self:
            menu.menu_cost = sum(menu.menu_line_ids.mapped('subtotal_cost'))
            _logger.debug(
                "Menu '%s' cost recomputed: %.2f", menu.name, menu.menu_cost
            )

    @api.depends('menu_sale_price', 'menu_cost')
    def _compute_margin(self):
        for menu in self:
            if menu.menu_sale_price:
                menu.margin_pct = (
                    (menu.menu_sale_price - menu.menu_cost) / menu.menu_sale_price
                ) * 100
            else:
                menu.margin_pct = 0.0

    @api.constrains('menu_sale_price')
    def _check_price(self):
        for rec in self:
            if rec.menu_sale_price < 0:
                raise ValidationError(_("Sale price cannot be negative."))


class WeddingMenuLine(models.Model):
    _name = 'dg.wedding.menu.line'
    _description = 'Menu Item Line'

    menu_id = fields.Many2one('dg.wedding.menu', string="Menu", ondelete='cascade')
    product_id = fields.Many2one(
        'product.template', string="Product / Ingredient", required=True
    )
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Qty per Person", default=1.0)
    unit = fields.Many2one('uom.uom', string="Unit", related='product_id.uom_id')

    product_cost = fields.Float(
        related='product_id.standard_price', string="Unit Cost", readonly=True
    )
    subtotal_cost = fields.Float(
        string="Subtotal Cost", compute='_compute_subtotal', store=True
    )

    @api.depends('quantity', 'product_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal_cost = line.quantity * line.product_cost
