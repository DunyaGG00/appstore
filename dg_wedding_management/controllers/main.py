import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class WeddingFloorPlanController(http.Controller):

    # ─── Helper: render a QWeb template as a full HTML response ───────────
    def _render_page(self, template, values):
        html = request.env['ir.ui.view']._render_template(template, values)
        return request.make_response(
            '<!DOCTYPE html>\n' + html,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    # ─────────────────────────────────────────────────────────────────────
    # HALL FLOOR PLAN  (design positions of physical tables)
    # Route: /dg_wedding_management/hall_plan/<hall_id>
    # ─────────────────────────────────────────────────────────────────────
    @http.route(
        '/dg_wedding_management/hall_plan/<int:hall_id>',
        type='http', auth='user', website=False,
    )
    def hall_plan(self, hall_id, **kwargs):
        hall = request.env['dg.wedding.hall'].browse(hall_id)
        if not hall.exists():
            return request.not_found()

        tables_data = []
        for t in hall.physical_table_ids:
            tables_data.append({
                'id': 'phys_%d' % t.id,
                'phys_id': t.id,
                'name': t.name,
                'shape': t.shape or 'round',
                'capacity': t.guest_capacity,
                'x': t.position_x or 15,
                'y': t.position_y or 40,
            })

        values = {
            'hall': hall,
            'mode': 'hall',
            'title': '%s — Layout Design' % hall.name,
            'back_label': '← Back to Hall',
            'back_url': '/odoo/dg-wedding-hall/%d' % hall_id,
            'save_url': '/dg_wedding_management/hall_plan/%d/save' % hall_id,
            'tables_json': json.dumps(tables_data),
            'waiters_json': json.dumps([]),
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
                if phys_id:
                    phys = request.env['dg.wedding.table'].browse(phys_id)
                    if phys.exists() and phys.hall_id.id == hall_id:
                        phys.write({
                            'position_x': int(tbl.get('x', 0)),
                            'position_y': int(tbl.get('y', 0)),
                        })
            _logger.info("Hall plan saved: %s — %d tables", hall.name, len(tables or []))
            return {'success': True}
        except Exception as e:
            _logger.exception("Error saving hall plan %d", hall_id)
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────────────────────────────
    # WEDDING FLOOR PLAN  (assign guests + waiters per event)
    # Route: /dg_wedding_management/floor_plan/<wedding_id>
    # ─────────────────────────────────────────────────────────────────────
    @http.route(
        '/dg_wedding_management/floor_plan/<int:wedding_id>',
        type='http', auth='user', website=False,
    )
    def wedding_floor_plan(self, wedding_id, **kwargs):
        wedding = request.env['dg.wedding'].browse(wedding_id)
        if not wedding.exists():
            return request.not_found()

        tables_data = []
        for line in wedding.table_line_ids:
            tables_data.append({
                'id': 'asgn_%d' % line.id,
                'assignment_id': line.id,
                'phys_id': line.table_id.id,
                'name': line.table_id.name,
                'shape': line.table_id.shape or 'round',
                'capacity': line.standard_capacity,
                'guests': line.actual_guests,
                'waiter': line.assigned_waiter_id.name if line.assigned_waiter_id else '',
                'waiter_id': line.assigned_waiter_id.id if line.assigned_waiter_id else 0,
                'vip': line.is_vip,
                'notes': line.special_notes or '',
                'x': line.table_id.position_x or 15,
                'y': line.table_id.position_y or 40,
            })

        # Waiters assigned to this wedding first, then all waiters as fallback
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
            'title': '%s — %s' % (wedding.name, wedding.couple_display or wedding.wedding_owner_name),
            'back_label': '← Back to Wedding',
            'back_url': '/odoo/dg-wedding/%d' % wedding_id,
            'save_url': '/dg_wedding_management/floor_plan/%d/save' % wedding_id,
            'tables_json': json.dumps(tables_data),
            'waiters_json': json.dumps(waiters),
            'csrf_token': request.csrf_token(),
        }
        return self._render_page('dg_wedding_management.floor_plan_template', values)

    @http.route(
        '/dg_wedding_management/floor_plan/<int:wedding_id>/save',
        type='json', auth='user', methods=['POST'],
    )
    def wedding_floor_plan_save(self, wedding_id, tables=None, **kwargs):
        wedding = request.env['dg.wedding'].browse(wedding_id)
        if not wedding.exists():
            return {'success': False, 'error': 'Wedding not found'}
        try:
            for tbl in (tables or []):
                assignment_id = tbl.get('assignment_id')
                phys_id = tbl.get('phys_id')
                if assignment_id:
                    asgn = request.env['dg.wedding.table.assignment'].browse(assignment_id)
                    if asgn.exists():
                        asgn.write({
                            'actual_guests': tbl.get('guests', 0),
                            'assigned_waiter_id': tbl.get('waiter_id') or False,
                            'is_vip': tbl.get('vip', False),
                            'special_notes': tbl.get('notes', ''),
                        })
                # Always sync position back to physical table
                if phys_id:
                    phys = request.env['dg.wedding.table'].browse(phys_id)
                    if phys.exists():
                        phys.write({
                            'position_x': int(tbl.get('x', 0)),
                            'position_y': int(tbl.get('y', 0)),
                        })
            _logger.info(
                "Wedding floor plan saved: %s — %d tables", wedding.name, len(tables or [])
            )
            return {'success': True}
        except Exception as e:
            _logger.exception("Error saving wedding floor plan %d", wedding_id)
            return {'success': False, 'error': str(e)}
