import json
import logging
from markupsafe import Markup
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WeddingFloorPlanController(http.Controller):

    def _render_page(self, template, values):
        html = request.env['ir.ui.view']._render_template(template, values)
        return request.make_response(
            '<!DOCTYPE html>\n' + html,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HALL FLOOR PLAN  –  design positions of physical tables
    # ─────────────────────────────────────────────────────────────────────────
    @http.route(
        '/dg_wedding_management/hall_plan/<int:hall_id>',
        type='http', auth='user', website=False,
    )
    def hall_plan(self, hall_id, **kwargs):
        hall = request.env['dg.wedding.hall'].browse(hall_id)
        if not hall.exists():
            return request.not_found()

        tables_data = []
        for i, t in enumerate(hall.physical_table_ids):
            x = t.position_x if t.position_x else (12 + ((i % 5) * 17))
            y = t.position_y if t.position_y else (38 + ((i // 5) * 24))
            tables_data.append({
                'id': 'phys_%d' % t.id,
                'phys_id': t.id,
                'assignment_id': 0,
                'name': t.name,
                'shape': t.shape or 'round',
                'capacity': t.guest_capacity,
                'guests': 0,
                'waiter': '',
                'waiter_id': 0,
                'vip': False,
                'notes': '',
                'x': x,
                'y': y,
            })

        values = {
            'hall': hall,
            'mode': 'hall',
            'title': '%s — Layout Design' % hall.name,
            'back_label': '← Back to Hall',
            'back_url': '/odoo/dg-wedding-hall/%d' % hall_id,
            'save_url': '/dg_wedding_management/hall_plan/%d/save' % hall_id,
            # Markup prevents QWeb from HTML-escaping the JSON inside <script>
            'tables_json': Markup(json.dumps(tables_data)),
            'waiters_json': Markup(json.dumps([])),
            'all_hall_tables_json': Markup(json.dumps([])),
            'csrf_token': request.csrf_token(),
        }
        return self._render_page('dg_wedding_management.floor_plan_template', values)

    @http.route(
        '/dg_wedding_management/hall_plan/<int:hall_id>/save',
        type='json', auth='user', methods=['POST'],
    )
    def hall_plan_save(self, hall_id, tables=None, **kwargs):
        hall = request.env['dg.wedding.hall'].browse(hall_id)
        if not hall.exists():
            return {'success': False, 'error': 'Hall not found'}
        try:
            for tbl in (tables or []):
                phys_id = tbl.get('phys_id')
                if not phys_id:
                    continue
                phys = request.env['dg.wedding.table'].browse(int(phys_id))
                if not phys.exists() or phys.hall_id.id != hall_id:
                    continue
                write_vals = {
                    'position_x': int(tbl.get('x', 0)),
                    'position_y': int(tbl.get('y', 0)),
                }
                if tbl.get('name'):
                    write_vals['name'] = str(tbl['name']).strip()
                if tbl.get('shape') in ('round', 'rectangular', 'oval', 'square'):
                    write_vals['shape'] = tbl['shape']
                if tbl.get('capacity'):
                    write_vals['guest_capacity'] = max(1, int(tbl['capacity']))
                phys.write(write_vals)
            _logger.info("Hall plan saved: %s — %d tables", hall.name, len(tables or []))
            return {'success': True}
        except Exception as e:
            _logger.exception("Error saving hall plan %d", hall_id)
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # WEDDING FLOOR PLAN  –  assign guests + waiters per event
    # ─────────────────────────────────────────────────────────────────────────
    @http.route(
        '/dg_wedding_management/floor_plan/<int:wedding_id>',
        type='http', auth='user', website=False,
    )
    def wedding_floor_plan(self, wedding_id, **kwargs):
        wedding = request.env['dg.wedding'].browse(wedding_id)
        if not wedding.exists():
            return request.not_found()

        # Build assigned table list
        assigned_phys_ids = set()
        tables_data = []
        for line in wedding.table_line_ids:
            phys = line.table_id
            assigned_phys_ids.add(phys.id)
            x = phys.position_x if phys.position_x else 15
            y = phys.position_y if phys.position_y else 40
            tables_data.append({
                'id': 'asgn_%d' % line.id,
                'assignment_id': line.id,
                'phys_id': phys.id,
                'name': phys.name,
                'shape': phys.shape or 'round',
                'capacity': line.standard_capacity or phys.guest_capacity,
                'guests': line.actual_guests,
                'waiter': line.assigned_waiter_id.name if line.assigned_waiter_id else '',
                'waiter_id': line.assigned_waiter_id.id if line.assigned_waiter_id else 0,
                'vip': line.is_vip,
                'notes': line.special_notes or '',
                'x': x,
                'y': y,
            })

        # Unassigned hall tables available to add
        all_hall_tables = []
        if wedding.hall_id:
            for i, t in enumerate(wedding.hall_id.physical_table_ids):
                if t.id not in assigned_phys_ids:
                    all_hall_tables.append({
                        'phys_id': t.id,
                        'name': t.name,
                        'shape': t.shape or 'round',
                        'capacity': t.guest_capacity,
                        'x': t.position_x if t.position_x else (12 + ((i % 5) * 17)),
                        'y': t.position_y if t.position_y else (38 + ((i // 5) * 24)),
                    })

        # Waiters: prefer those already on this wedding, fall back to all waiters
        waiter_emps = wedding.employee_line_ids.filtered(
            lambda l: l.role == 'waiter'
        ).mapped('employee_id')
        if not waiter_emps:
            waiter_emps = request.env['dg.wedding.employee'].search(
                [('employee_type', '=', 'waiter')]
            )
        waiters = [{'id': e.id, 'name': e.name} for e in waiter_emps]

        values = {
            'wedding': wedding,
            'hall': wedding.hall_id,
            'mode': 'wedding',
            'title': '%s — %s' % (
                wedding.name,
                wedding.couple_display or wedding.wedding_owner_name,
            ),
            'back_label': '← Back to Wedding',
            'back_url': '/odoo/dg-wedding/%d' % wedding_id,
            'save_url': '/dg_wedding_management/floor_plan/%d/save' % wedding_id,
            # Markup prevents QWeb from HTML-escaping the JSON inside <script>
            'tables_json': Markup(json.dumps(tables_data)),
            'waiters_json': Markup(json.dumps(waiters)),
            'all_hall_tables_json': Markup(json.dumps(all_hall_tables)),
            'csrf_token': request.csrf_token(),
        }
        return self._render_page('dg_wedding_management.floor_plan_template', values)

    @http.route(
        '/dg_wedding_management/floor_plan/<int:wedding_id>/save',
        type='json', auth='user', methods=['POST'],
    )
    def wedding_floor_plan_save(self, wedding_id, tables=None, removed_ids=None, **kwargs):
        wedding = request.env['dg.wedding'].browse(wedding_id)
        if not wedding.exists():
            return {'success': False, 'error': 'Wedding not found'}
        try:
            TableAssignment = request.env['dg.wedding.table.assignment']
            PhysTable = request.env['dg.wedding.table']

            # 1. Delete assignments that were removed in the UI
            if removed_ids:
                to_remove = TableAssignment.browse([int(i) for i in removed_ids if i])
                valid = to_remove.filtered(
                    lambda r: r.exists() and r.wedding_id.id == wedding_id
                )
                valid.unlink()

            # 2. Update existing / create new assignments
            saved = 0
            for tbl in (tables or []):
                assignment_id = tbl.get('assignment_id') or 0
                phys_id = tbl.get('phys_id') or 0

                waiter_id = int(tbl.get('waiter_id') or 0) or False

                if assignment_id:
                    # Update existing assignment
                    asgn = TableAssignment.browse(int(assignment_id))
                    if asgn.exists() and asgn.wedding_id.id == wedding_id:
                        asgn.write({
                            'actual_guests': int(tbl.get('guests', 0)),
                            'assigned_waiter_id': waiter_id,
                            'is_vip': bool(tbl.get('vip', False)),
                            'special_notes': tbl.get('notes', '') or '',
                        })
                        saved += 1

                elif phys_id:
                    # Create new assignment (table was added from the floor plan UI)
                    phys = PhysTable.browse(int(phys_id))
                    if (phys.exists()
                            and wedding.hall_id
                            and phys.hall_id.id == wedding.hall_id.id):
                        # Guard against duplicates
                        already = TableAssignment.search([
                            ('wedding_id', '=', wedding_id),
                            ('table_id', '=', int(phys_id)),
                        ], limit=1)
                        if not already:
                            TableAssignment.create({
                                'wedding_id': wedding_id,
                                'table_id': int(phys_id),
                                'actual_guests': int(tbl.get('guests', 0)),
                                'assigned_waiter_id': waiter_id,
                                'is_vip': bool(tbl.get('vip', False)),
                                'special_notes': tbl.get('notes', '') or '',
                            })
                            saved += 1

                # Always sync physical table position
                if phys_id:
                    phys = PhysTable.browse(int(phys_id))
                    if phys.exists():
                        phys.write({
                            'position_x': int(tbl.get('x', 0)),
                            'position_y': int(tbl.get('y', 0)),
                        })

            _logger.info(
                "Wedding floor plan saved: %s — %d tables", wedding.name, saved
            )
            return {'success': True, 'saved': saved}
        except Exception as e:
            _logger.exception("Error saving wedding floor plan %d", wedding_id)
            return {'success': False, 'error': str(e)}
