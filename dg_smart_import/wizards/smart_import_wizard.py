import base64
import csv
import io
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

# Field types that cannot be meaningfully imported from a flat file
_SKIP_TTYPES = frozenset({'one2many', 'many2many', 'binary', 'reference', 'properties'})


class SmartImportMappingLine(models.TransientModel):
    """One row in the column-to-field mapping table inside the wizard."""

    _name = 'dg.smart.import.mapping.line'
    _description = 'Smart Import Field Mapping Line'
    _order = 'id'

    wizard_id = fields.Many2one(
        'dg.smart.import.wizard',
        required=True,
        ondelete='cascade',
    )
    file_column = fields.Char(string="File Column", readonly=True)
    sample_value = fields.Char(string="Sample Value", readonly=True)
    field_id = fields.Many2one(
        'ir.model.fields',
        string="Map to Field",
    )
    # Computed Char (not related) to avoid type mismatch with Selection field ttype
    field_ttype = fields.Char(
        string="Field Type",
        compute='_compute_field_ttype',
        readonly=True,
    )

    @api.depends('field_id')
    def _compute_field_ttype(self):
        for line in self:
            line.field_ttype = line.field_id.ttype if line.field_id else ''


class SmartImportWizard(models.TransientModel):
    """
    Generic Smart Import wizard.

    Workflow:
      1. upload  – user sees model fields list + uploads a CSV/Excel file
      2. map     – user maps file columns to model fields
      3. preview – first 10 rows shown for confirmation
      4. done    – import executed; summary displayed

    All step-transition buttons return False so Odoo refreshes the dialog
    in-place (no stacking/misrouting of act_window actions).
    """

    _name = 'dg.smart.import.wizard'
    _description = 'Smart Import Wizard'

    # ── Core fields ────────────────────────────────────────────────────────────

    model_id = fields.Many2one(
        'ir.model',
        string="Target Model",
        required=True,
        readonly=True,
    )
    model_name = fields.Char(
        related='model_id.model',
        string="Technical Name",
        readonly=True,
    )
    state = fields.Selection(
        [
            ('upload', 'Upload'),
            ('map', 'Map Fields'),
            ('preview', 'Preview'),
            ('done', 'Done'),
        ],
        default='upload',
        string="Step",
        readonly=True,
    )

    # ── File upload ────────────────────────────────────────────────────────────

    file_data = fields.Binary(string="File", attachment=False)
    file_name = fields.Char(string="File Name")

    # ── Step 1: Model field reference (shown before file upload) ───────────────

    field_info_html = fields.Html(
        string="Available Model Fields",
        compute='_compute_field_info_html',
        readonly=True,
        sanitize=False,
    )

    @api.depends('model_id')
    def _compute_field_info_html(self):
        for wiz in self:
            if not wiz.model_id:
                wiz.field_info_html = ''
                continue
            importable = self.env['ir.model.fields'].search([
                ('model_id', '=', wiz.model_id.id),
                ('store', '=', True),
                ('ttype', 'not in', list(_SKIP_TTYPES)),
            ], order='field_description')

            rows = []
            for f in importable:
                ttype_badge = (
                    f'<span class="badge rounded-pill bg-secondary '
                    f'text-uppercase" style="font-size:0.68em">{f.ttype}</span>'
                )
                rows.append(
                    f'<tr>'
                    f'<td>{f.field_description}</td>'
                    f'<td><code style="font-size:0.85em">{f.name}</code></td>'
                    f'<td>{ttype_badge}</td>'
                    f'</tr>'
                )

            wiz.field_info_html = (
                '<div style="max-height:320px;overflow-y:auto">'
                '<table class="table table-sm table-bordered table-hover mb-0">'
                '<thead class="table-light">'
                '<tr><th>Label</th><th>Technical Name</th><th>Type</th></tr>'
                '</thead>'
                '<tbody>'
                + ''.join(rows) +
                '</tbody></table></div>'
            )

    # ── Mapping ────────────────────────────────────────────────────────────────

    mapping_line_ids = fields.One2many(
        'dg.smart.import.mapping.line',
        'wizard_id',
        string="Column Mapping",
    )

    # ── Preview ────────────────────────────────────────────────────────────────

    preview_html = fields.Html(
        string="Data Preview",
        readonly=True,
        sanitize=False,
    )

    # ── Results ────────────────────────────────────────────────────────────────

    import_success_count = fields.Integer(string="Imported", readonly=True)
    import_error_count = fields.Integer(string="Failed", readonly=True)
    import_log = fields.Text(string="Import Log", readonly=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    @api.model
    def action_open_wizard(self, model_name):
        """
        Entry point called from the bound server action.
        Creates a fresh wizard and returns an extra-large dialog action.
        """
        ir_model = self.env['ir.model'].search(
            [('model', '=', model_name)], limit=1
        )
        if not ir_model:
            raise UserError(_("Model not found: %s") % model_name)

        config = self.env['dg.smart.import.config'].search(
            [('model_id', '=', ir_model.id), ('enabled', '=', True)], limit=1
        )
        if not config:
            raise UserError(
                _("Smart Import is not enabled for model '%s'. "
                  "Go to Smart Import → Configuration to activate it.")
                % ir_model.name
            )

        wizard = self.create({'model_id': ir_model.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _("Smart Import — %s") % ir_model.name,
            'res_model': 'dg.smart.import.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }

    # ── Wizard step actions ────────────────────────────────────────────────────
    # Each button returns _reopen() which closes the current dialog and
    # immediately reopens the same wizard record — this is required in Odoo 18
    # because returning False from a TransientModel button closes the dialog.

    def action_parse_file(self):
        """Step 1 → 2: parse the uploaded file and build the mapping table."""
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please upload a CSV or Excel (.xlsx) file first."))

        columns, rows = self._parse_file()
        if not columns:
            raise UserError(_("The file appears to be empty or has no header row."))

        # Rebuild mapping lines from the file's column headers
        self.mapping_line_ids.unlink()
        mapping_vals = []
        for col in columns:
            sample = ''
            if rows:
                raw = rows[0].get(col, '')
                sample = str(raw)[:150] if raw is not None else ''
            mapping_vals.append({
                'wizard_id': self.id,
                'file_column': col,
                'sample_value': sample,
            })
        self.env['dg.smart.import.mapping.line'].create(mapping_vals)
        self.state = 'map'
        return self._reopen()

    def action_preview(self):
        """Step 2 → 3: build an HTML preview of the first 10 data rows."""
        self.ensure_one()
        mapped_lines = [l for l in self.mapping_line_ids if l.field_id]
        if not mapped_lines:
            raise UserError(
                _("Please map at least one column to a model field before previewing.")
            )

        # Block preview if required fields with no default are unmapped
        missing = self._get_unmapped_required_fields()
        if missing:
            raise UserError(
                _("The following required fields are not mapped and have no default value:\n\n%s\n\n"
                  "Add these columns to your file, or map them before proceeding.")
                % '\n'.join(f"• {label} ({fname})" for fname, label in missing)
            )

        _, rows = self._parse_file()
        preview_rows = rows[:10]

        parts = [
            '<div style="overflow-x:auto">',
            '<table class="table table-sm table-bordered table-hover mb-0">',
            '<thead class="table-primary"><tr>',
        ]
        for line in mapped_lines:
            parts.append(
                f'<th class="text-nowrap">{line.file_column}'
                f'<br/><small class="fw-normal opacity-75">'
                f'→ {line.field_id.field_description} '
                f'<em>({line.field_ttype})</em></small></th>'
            )
        parts.append('</tr></thead><tbody>')

        for row in preview_rows:
            parts.append('<tr>')
            for line in mapped_lines:
                val = row.get(line.file_column, '')
                parts.append(f'<td>{val}</td>')
            parts.append('</tr>')

        if not preview_rows:
            colspan = len(mapped_lines)
            parts.append(
                f'<tr><td colspan="{colspan}" class="text-center text-muted">'
                'No data rows found.</td></tr>'
            )

        parts.extend(['</tbody></table>', '</div>'])
        self.preview_html = ''.join(parts)
        self.state = 'preview'
        return self._reopen()

    def action_import(self):
        """Step 3 → 4: import all rows into the target model."""
        self.ensure_one()

        mapping = {
            line.file_column: line.field_id
            for line in self.mapping_line_ids
            if line.field_id
        }
        if not mapping:
            raise UserError(_("No column mappings defined. Nothing to import."))

        _, rows = self._parse_file()
        TargetModel = self.env[self.model_name]

        success = 0
        errors = []

        for row_num, row in enumerate(rows, start=2):  # row 1 = header
            try:
                vals = {}
                for col, field in mapping.items():
                    raw = row.get(col)
                    vals[field.name] = self._convert_value(raw, field)
                # Use a savepoint so a DB-level error on one row only rolls back
                # that row and leaves the outer transaction intact.
                with self.env.cr.savepoint():
                    TargetModel.create(vals)
                success += 1
            except Exception as exc:
                msg = f"Row {row_num}: {exc}"
                errors.append(msg)
                _logger.warning("Smart Import — %s", msg)

        log_lines = [f"Imported {success} record(s) successfully."]
        if errors:
            log_lines.append(f"Failed: {len(errors)} record(s).")
            log_lines.append("")
            log_lines.extend(errors[:100])
            if len(errors) > 100:
                log_lines.append(
                    f"… and {len(errors) - 100} more error(s) (truncated)."
                )

        self.import_success_count = success
        self.import_error_count = len(errors)
        self.import_log = '\n'.join(log_lines)
        self.state = 'done'
        return self._reopen()

    def action_back_to_upload(self):
        self.ensure_one()
        # Clear file + mapping so the user must upload fresh — avoids silently
        # re-using a stale file from a previous attempt.
        self.mapping_line_ids.unlink()
        self.write({'file_data': False, 'file_name': False, 'state': 'upload'})
        return self._reopen()

    def action_back_to_map(self):
        self.ensure_one()
        self.state = 'map'
        return self._reopen()

    # ── Validation helpers ─────────────────────────────────────────────────────

    # ORM system fields that are always auto-populated — never require mapping.
    _SYSTEM_FIELDS = frozenset({
        'id', 'create_uid', 'write_uid', 'create_date', 'write_date',
        'display_name', '__last_update', 'active',
    })

    def _get_unmapped_required_fields(self):
        """
        Return a list of ``(technical_name, label)`` tuples for every required
        field on the target model that:
          - is NOT mapped in the current mapping lines, AND
          - has NO default value defined at the ORM level.

        Fields with defaults (even ``default=False``) are excluded because
        the ORM will supply a value automatically.
        """
        mapped_names = {
            line.field_id.name
            for line in self.mapping_line_ids
            if line.field_id
        }
        TargetModel = self.env[self.model_name]
        missing = []
        for fname, field in TargetModel._fields.items():
            if (
                fname not in self._SYSTEM_FIELDS
                and fname not in mapped_names
                and field.required
                and field.default is None  # no ORM-level default
            ):
                missing.append((fname, field.string or fname))
        return missing

    # ── Dialog helper ──────────────────────────────────────────────────────────

    def _reopen(self):
        """
        Close the current dialog and reopen this same wizard record.

        Returning False from a TransientModel button closes the dialog in Odoo 18,
        so we must explicitly reopen the record to keep the wizard alive across steps.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _("Smart Import — %s") % self.model_id.name,
            'res_model': 'dg.smart.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }

    # ── File parsing ───────────────────────────────────────────────────────────

    def _parse_file(self):
        """
        Return ``(columns: list[str], rows: list[dict])`` from the uploaded file.

        Auto-detects CSV vs XLSX by filename extension; falls back to magic bytes.
        """
        if not self.file_data:
            raise UserError(_("No file uploaded."))

        # fields.Binary returns a base64-encoded value from the ORM in Odoo 18
        raw = base64.b64decode(self.file_data)

        fname = (self.file_name or '').lower()
        if fname.endswith('.xlsx') or fname.endswith('.xls'):
            return self._parse_excel(raw)
        if fname.endswith('.csv'):
            return self._parse_csv(raw)

        # Auto-detect: XLSX is a ZIP (magic PK\x03\x04)
        if raw[:4] == b'PK\x03\x04':
            return self._parse_excel(raw)
        return self._parse_csv(raw)

    @staticmethod
    def _parse_csv(raw_bytes):
        """Decode and parse a CSV; auto-detects encoding and delimiter."""
        text = None
        for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw_bytes.decode('latin-1', errors='replace')

        sample = text[:4096]
        counts = {',': sample.count(','), ';': sample.count(';'), '\t': sample.count('\t')}
        delimiter = max(counts, key=counts.get)

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
        return columns, rows

    @staticmethod
    def _parse_excel(raw_bytes):
        """Parse XLSX using openpyxl."""
        try:
            import openpyxl
        except ImportError as exc:
            raise UserError(
                _("The openpyxl library is required for Excel imports. "
                  "Install it with: pip install openpyxl")
            ) from exc

        wb = openpyxl.load_workbook(
            io.BytesIO(raw_bytes), read_only=True, data_only=True
        )
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)

        header_row = next(rows_iter, [])
        headers = [
            str(h).strip() if h is not None else f"col_{i}"
            for i, h in enumerate(header_row)
        ]

        rows = []
        for row_vals in rows_iter:
            if all(v is None for v in row_vals):
                continue
            row_dict = {
                h: (str(v) if v is not None else '')
                for h, v in zip(headers, row_vals)
            }
            rows.append(row_dict)

        wb.close()
        return headers, rows

    # ── Value conversion ───────────────────────────────────────────────────────

    def _convert_value(self, raw_value, field):
        """
        Convert a raw cell value to the Python type the ORM field expects.
        Raises ValueError on failure (caller logs per-row without crashing).
        """
        ttype = field.ttype

        if raw_value is None or raw_value == '':
            return False

        str_val = str(raw_value).strip()
        if not str_val:
            return False

        if ttype in ('char', 'text', 'html'):
            return str_val

        if ttype == 'integer':
            try:
                return int(float(str_val.replace(',', '.')))
            except (ValueError, TypeError):
                raise ValueError(
                    f"Cannot convert {str_val!r} to integer "
                    f"for field '{field.field_description}'"
                )

        if ttype in ('float', 'monetary'):
            try:
                return float(str_val.replace(',', '.'))
            except (ValueError, TypeError):
                raise ValueError(
                    f"Cannot convert {str_val!r} to float "
                    f"for field '{field.field_description}'"
                )

        if ttype == 'boolean':
            return str_val.lower() in ('true', '1', 'yes', 'oui', 'vrai', 'x', 'on')

        if ttype == 'date':
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y'):
                try:
                    return datetime.strptime(str_val, fmt).strftime(
                        DEFAULT_SERVER_DATE_FORMAT
                    )
                except ValueError:
                    continue
            raise ValueError(
                f"Cannot parse date {str_val!r} for field '{field.field_description}'. "
                "Supported formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY"
            )

        if ttype == 'datetime':
            for fmt in (
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d',
            ):
                try:
                    return datetime.strptime(str_val, fmt).strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT
                    )
                except ValueError:
                    continue
            raise ValueError(
                f"Cannot parse datetime {str_val!r} for field '{field.field_description}'."
            )

        if ttype == 'many2one':
            comodel = field.relation
            rec = self.env[comodel].search([('name', '=', str_val)], limit=1)
            if not rec:
                rec = self.env[comodel].search([('name', 'ilike', str_val)], limit=1)
            if rec:
                return rec.id
            raise ValueError(
                f"No record in '{comodel}' matches {str_val!r} "
                f"for field '{field.field_description}'"
            )

        if ttype == 'selection':
            model_field = self.env[self.model_name]._fields.get(field.name)
            if model_field and isinstance(model_field.selection, list):
                for key, label in model_field.selection:
                    if str_val == key:
                        return key
                    if str_val.lower() == str(label).lower():
                        return key
            return str_val

        return str_val
