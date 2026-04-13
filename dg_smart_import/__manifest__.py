{
    'name': 'DG Smart Import',
    'version': '18.0.1.0.0',
    'summary': 'Import CSV & Excel into any Odoo model — visual field mapping, preview & error log',
    'description': """
DG Smart Import
===============

A fully generic import wizard that works with **any Odoo model** — no coding required.

Key Features
------------
- Enable Smart Import per-model from a central configuration screen
- Upload CSV or Excel (.xlsx) files
- Visual column-to-field mapping with type hints and sample values
- Required-field validation before you commit
- 10-row data preview before importing
- Per-row savepoint isolation — one bad row never blocks the rest
- Detailed import log: success count, failure count, per-row error messages
- Many2one matched by name (exact then case-insensitive fallback)
- Selection fields matched by key or label
- Date / datetime auto-detection across common formats
- Group-based access control (Smart Import Manager)
- Dynamic server action injected into list & form views automatically
    """,
    'category': 'Technical',
    'author': 'Red Bridge ERP',
    'website': 'https://redbridgeerp.com',
    'support': 'dunyamaligoyushlu00@gmail.com',
    'license': 'OPL-1',
    'price': 99.0,
    'currency': 'EUR',
    'depends': ['base'],
    'data': [
        'security/dg_smart_import_groups.xml',
        'security/ir.model.access.csv',
        'views/smart_import_config_views.xml',
        'views/menus.xml',
        'wizards/smart_import_wizard_views.xml',
    ],
    'images': [
        'static/description/banner.png',
        'static/description/screen_step1.png',
        'static/description/screen_step2.png',
        'static/description/screen_step3.png',
        'static/description/screen_done.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'web_icon': 'dg_smart_import,static/description/icon.png',
}
