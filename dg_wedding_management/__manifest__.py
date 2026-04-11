{
    'name': 'DG Wedding Management',
    'version': '18.0.1.1.0',
    'summary': 'Complete Wedding Hall & Event Management — Floor Plan, Staff, Financials & Reports',
    'description': """
        Full-featured wedding management system for halls and event venues:
        - Wedding event lifecycle (Quotation → Confirmed → In Progress → Completed)
        - Hall & physical table management with drag-and-drop interactive floor plan
        - Staff assignment with per-event fixed-fee payment tracking
        - Menu packages with per-guest pricing
        - Full financial dashboard: revenue, expenses, deposits, net profit
        - PDF summary reports with custom wizard
        - Table assignment wizard with waiter and VIP seat management
        - Hall double-booking prevention
        - Kanban, List and Form views with status ribbons
        - 75 automated tests included
    """,
    'category': 'Services/Events',
    'author': 'Red Bridge ERP',
    'website': 'https://redbridgeerp.com',
    'license': 'OPL-1',
    'price': 150.0,
    'currency': 'EUR',
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
    'images': [
        'static/description/main_screenshot.png',
        'static/description/screen_kanban.png',
        'static/description/screen_floor_plan.png',
        'static/description/screen_financials.png',
        'static/description/screen_staff.png',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
