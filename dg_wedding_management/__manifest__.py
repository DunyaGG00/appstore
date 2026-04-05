{
    'name': 'DG Wedding Management',
    'version': '18.0.1.0.0',
    'summary': 'Comprehensive Wedding Hall & Event Management',
    'description': """
        Full-featured wedding management system:
        - Wedding event lifecycle (draft → confirmed → in_progress → done)
        - Hall & table management with interactive floor plan
        - Staff assignment (waiters, chefs, security, etc.)
        - Menu & cost tracking
        - Financial reporting (revenue, cost, profit)
        - PDF reports for every model
        - Wizards for table assignment & report generation
    """,
    'category': 'Services/Events',
    'author': 'DG',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'product', 'account', 'uom'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/menu_views.xml',
        'views/employee_views.xml',
        'views/hall_views.xml',
        'views/table_views.xml',
        'views/wedding_views.xml',
        'views/menus.xml',
        'wizards/table_assignment_wizard_views.xml',
        'wizards/report_wizard_views.xml',
        'reports/report_templates.xml',
        'reports/report_actions.xml',
        'views/templates/floor_plan_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dg_wedding_management/static/src/css/wedding_theme.css',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
