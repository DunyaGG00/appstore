DG Wedding Management
=====================

A complete wedding hall and event management module for Odoo 18. Designed for
wedding venues, event halls, and catering businesses that need to manage the
full lifecycle of a wedding event from first enquiry to final completion.

.. contents::
   :local:
   :depth: 2


Installation
------------

1. Copy the ``dg_wedding_management`` folder into your Odoo ``addons`` path.
2. Restart the Odoo server.
3. Go to **Apps**, search for *DG Wedding Management*, and click **Install**.

The module depends on: ``base``, ``mail``, ``product``, ``account``, ``uom``.
No third-party Python packages are required.


Quick Start
-----------

**Step 1 — Set up your halls**

Navigate to **Wedding → Configuration → Halls** and create your venues.
For each hall, define a name, a short code, a base hire fee, and optionally
add physical tables (number, shape, capacity, floor-plan position).

**Step 2 — Create menu packages**

Go to **Wedding → Configuration → Menus** and add your packages.
Each package has a per-guest sale price that is multiplied automatically
against the confirmed guest count on each event.

**Step 3 — Add staff members**

Open **Wedding → Configuration → Staff** and create your team.
Set the employee type (waiter, chef, MC, security, photographer, other),
the payment type (per event or monthly salary), and the per-event fee.

**Step 4 — Create a wedding event**

Open **Wedding → Weddings**, click **New**, and fill in the client details,
couple names, hall, date/time, expected guest count, menu, and earnings.
Save the record — an automatic reference (``WED/YYYY/XXXX``) is assigned.

**Step 5 — Confirm and manage the event**

- Click **Confirm** to move the event from *Quotation* to *Confirmed*.
- Use the **Staff** tab to assign team members.
- Use the **Table Plan** tab to assign hall tables and set per-table guest counts.
- Click **Floor Plan** to open the interactive drag-and-drop canvas.
- Click **Start Event** on the day of the wedding.
- Click **Mark Completed** when finished.


Event Workflow
--------------

::

    draft  →  confirmed  →  in_progress  →  done
               ↓                                ↑
             cancel  →  (reset_to_draft)  ──────┘ (not allowed from done)

+----------------+---------------------------------------------+
| State          | Description                                 |
+================+=============================================+
| draft          | Quotation / initial enquiry                 |
+----------------+---------------------------------------------+
| confirmed      | Booking confirmed, hall reserved            |
+----------------+---------------------------------------------+
| in_progress    | Event is actively running                   |
+----------------+---------------------------------------------+
| done           | Event completed successfully                |
+----------------+---------------------------------------------+
| cancel         | Booking cancelled; can be reset to draft    |
+----------------+---------------------------------------------+

.. note::
   Hall double-booking is checked on confirmation. Two *draft* events may
   share the same hall and time slot, but confirming both will raise an error.


Interactive Floor Plan
----------------------

Each wedding event has a **Floor Plan** button in the header that opens a
dedicated canvas page. Features:

- Drag tables to reposition them.
- Click a table to open the detail panel (waiter assignment, VIP flag, guest count, notes).
- Use **+ Add Table** (dropdown) to add unassigned hall tables to the plan.
- Use **Remove Table** in the detail panel to unassign a table from the event.
- Click **Save Layout** to persist positions and assignments back to Odoo.
- Touch/mobile drag is fully supported.

.. warning::
   The floor plan serves the layout via a custom HTTP controller. The Odoo
   web client must be running and the user must be authenticated.


Financial Fields
----------------

+------------------+----------------------------------------------------------+
| Field            | Computation                                              |
+==================+==========================================================+
| menu_revenue     | ``menu_sale_price × confirmed_guests``                   |
+------------------+----------------------------------------------------------+
| hall_hire_fee    | Copied from the selected hall (editable)                 |
+------------------+----------------------------------------------------------+
| wedding_earnings | Manual entry (total client payment)                      |
+------------------+----------------------------------------------------------+
| total_cost       | ``hall_hire_fee + staff_fees + extra_expenses``          |
+------------------+----------------------------------------------------------+
| net_profit       | ``wedding_earnings − total_cost``                        |
+------------------+----------------------------------------------------------+
| balance_due      | ``wedding_earnings − deposit_amount``                    |
+------------------+----------------------------------------------------------+


Staff Payment Model
-------------------

Staff members have two payment types:

- **Per Event (Fixed Fee)** — a fixed ``event_fee`` is set on the employee
  and copied to each assignment. ``total_to_pay = event_fee``.
  Hours worked can be tracked separately but do not affect the fee.
- **Monthly Salary** — the employee is on a monthly contract.
  Their ``total_to_pay`` for any single event is ``0.00``; their overall
  salary is tracked on the employee record via ``monthly_wage``.


PDF Reports
-----------

Open the **Report** stat button on a wedding form, or click **Print Summary**
in the header. The wizard lets you choose:

- **Summary** — full event overview (client, couple, hall, guests, financials).
- **Financial** — revenue, cost breakdown, and profit statement.
- **Staff** — assigned staff list with roles and fees.

An optional date range filter is available for financial and staff reports.


Running the Test Suite
----------------------

.. code-block:: bash

    ./odoo-bin -c /path/to/odoo.conf -d your_db \
        -u dg_wedding_management \
        --test-enable --stop-after-init \
        --test-tags /dg_wedding_management

75 tests cover:

- Wedding lifecycle (state machine, date constraints, double-booking)
- Financial computations (menu revenue, balance due, total cost, net profit)
- Staff payment model (per-event fee, monthly, hours independence)
- Physical table constraints (capacity, shape, positions)
- Table assignment (occupancy %, VIP, waiter, duplicates)


Configuration Reference
-----------------------

**Halls** (``dg.wedding.hall``)
  Name, code, base hire fee, total capacity, active flag, and a
  one-to-many list of physical tables.

**Physical Tables** (``dg.wedding.table``)
  Name, hall, shape (round/rectangular/oval/square), standard capacity,
  floor-plan X/Y position (0–100 grid), notes, active flag.

**Staff** (``dg.wedding.employee``)
  Name, type, phone, email, ID number, address, payment type,
  monthly wage or per-event fee, photo, internal notes.

**Menus** (``dg.wedding.menu``)
  Package name, per-guest sale price, description, active flag.

**Wedding Event** (``dg.wedding``)
  Full event record — see *Quick Start* above for all fields.


Changelog
---------

18.0.1.1.0 (2026-04-11)
  - Floor plan: add/remove tables, drag-and-drop repositioning, touch support.
  - Payment model changed from hourly to per-event fixed fee.
  - Added ``currency_id`` to staff employee model.
  - Routing fix: added ``path`` key to main window actions.
  - Fixed ``@api.constrains`` on related fields.
  - Added 75 automated tests.
  - Accessibility improvements (ARIA roles, icon titles).

18.0.1.0.0 (2026-04-09)
  - Initial release.
