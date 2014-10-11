# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields
from openerp import SUPERUSER_ID

class HrAnalyticTimesheet(orm.Model):
    """
    Add field:
    - hr_analytic_timesheet_id:
    This field is added to make sure a hr.analytic.timesheet can be used
    instead of a project.task.work.

    This field will always return false as we want to by pass next operations
    in project.task write method.

    Without this field, it is impossible to write a project.task in which
    work_ids is empty as a check on it would raise an AttributeError.

    This is because, in project_timesheet module, project.task's write method
    checks if there is an hr_analytic_timesheet_id on each work_ids.

        (project_timesheet.py, line 250, in write)
        if not task_work.hr_analytic_timesheet_id:
            continue

    But as we redefine work_ids to be a relation to hr_analytic_timesheet
    instead of project.task.work, hr_analytic_timesheet doesn't exists
    in hr_analytic_timesheet... so it fails.

    An other option would be to monkey patch the project.task's write method...
    As this method doesn't fit with the change of work_ids relation in model.
    """
    _inherit = "hr.analytic.timesheet"
    _name = "hr.analytic.timesheet"

    def on_change_unit_amount(self, cr, uid, sheet_id, prod_id, unit_amount, company_id,
                              unit=False, journal_id=False, task_id=False, to_invoice=False,
                              context=None):
        res = super(HrAnalyticTimesheet, self).on_change_unit_amount(cr,
                                                                     uid,
                                                                     sheet_id,
                                                                     prod_id,
                                                                     unit_amount,
                                                                     company_id,
                                                                     unit,
                                                                     journal_id,
                                                                     context)
        if 'value' in res and task_id:
            task_obj = self.pool.get('project.task')
            p = task_obj.browse(cr, uid, task_id).project_id
            if p:
                res['value']['account_id'] = p.analytic_account_id.id
                if p.to_invoice and not to_invoice:
                    res['value']['to_invoice'] = p.to_invoice.id
        return res

    def _get_dummy_hr_analytic_timesheet_id(self, cr, uid, ids, names, arg, context=None):
        """
        Ensure all hr_analytic_timesheet_id is always False
        """
        return dict.fromkeys(ids, False)

    
    def _get_hr_timesheet_sheet(self, cr, uid, ids, context=None):
        ts_line_ids = []
        for ts in self.browse(cr, uid, ids, context=context):
            cr.execute("""
                    SELECT l.id
                        FROM hr_analytic_timesheet l
                    INNER JOIN account_analytic_line al
                        ON (l.line_id = al.id)
                    WHERE %(date_to)s >= al.date
                        AND %(date_from)s <= al.date
                        AND %(user_id)s = al.user_id
                    GROUP BY l.id""", {'date_from': ts.date_from,
                                        'date_to': ts.date_to,
                                        'user_id': ts.employee_id.user_id.id,})
            ts_line_ids.extend([row[0] for row in cr.fetchall()])
        return ts_line_ids

    _columns = {
        'hr_analytic_timesheet_id': fields.function(_get_dummy_hr_analytic_timesheet_id,
                                                        string='Related Timeline Id',
                                                        type='boolean'),
        'state' : fields.related('sheet_id','state',type="selection", selection=[
            ('new', 'Pending'),
            ('draft','Pending'),
            ('confirm','Pending'),
            ('done','Confirmed'),
            ('posted', 'Posted')], string="Timesheet State",
            store = {
                    'hr_timesheet_sheet.sheet': (_get_hr_timesheet_sheet, ['state'], 10),
                    'hr.analytic.timesheet': (lambda self,cr,uid,ids,context=None: ids, None, 10),
                  },
            ),
        'task_id': fields.many2one('project.task', 'Task')
    }

    def _check_task_project(self, cr, uid, ids):
        for line in self.browse(cr, uid, ids):
            if line.task_id and line.account_id:
                if line.task_id.project_id.analytic_account_id.id != line.account_id.id:
                    return False
        return True

    _constraints = [
        (_check_task_project, 'Error! Task must belong to the project.', ['task_id','account_id']),
    ]


    def _trigger_projects(self, cr, uid, task_ids, context=None):
        t_obj = self.pool['project.task']
        for task in t_obj.browse(cr, SUPERUSER_ID, task_ids, context=context):
            project = task.project_id
            task.write({'name':task.name})
            project.write({'parent_id': project.parent_id.id})
        return task_ids

    def _set_remaining_hours_create(self, cr, uid, vals, context=None):
        if not vals.get('task_id'):
            return
        hours = vals.get('unit_amount', 0.0)
        
        # We can not do a write else we will have a recursion error
        cr.execute('update project_task set remaining_hours= \
                    (CASE \
                       When ((remaining_hours - %s)<0) \
                       THEN 0.0 \
                       ELSE (remaining_hours - %s) \
                    END)\
                    where id=%s',
                   (hours, hours, vals['task_id']))
        self._trigger_projects(cr, uid, [vals['task_id']], context=context)
        return vals

    def _set_remaining_hours_write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids):
            # in OpenERP if we set a value to nil vals become False
            old_task_id = line.task_id and line.task_id.id or None
            # if no task_id in vals we assume it is equal to old
            new_task_id = vals.get('task_id', old_task_id)
            # we look if value has changed
            if (new_task_id != old_task_id) and old_task_id:
                self._set_remaining_hours_unlink(cr, uid, [line.id], context)
                if new_task_id:
                    data = {'task_id': new_task_id,
                            'to_invoice': vals.get('to_invoice',
                                               line.to_invoice and line.to_invoice.id or False),
                            'unit_amount': vals.get('unit_amount', line.unit_amount)}
                    self._set_remaining_hours_create(cr, uid, data, context)
                    self._trigger_projects(cr, uid, list(set([old_task_id, new_task_id])),
                                           context=context)
                return ids
            if new_task_id:
                hours = vals.get('unit_amount', line.unit_amount)
                old_hours = line.unit_amount if old_task_id else 0.0
                # We can not do a write else we will have a recursion error
                cr.execute('update project_task set remaining_hours=remaining_hours - %s + (%s) where id=%s',
                           (hours, old_hours, new_task_id))
                self._trigger_projects(cr, uid, [new_task_id], context=context)

        return ids

    def _set_remaining_hours_unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = False
        for line in self.browse(cr, uid, ids):
            if not line.task_id:
                continue
            hours = line.unit_amount or 0.0
            task_id = line.task_id.id
            cr.execute('update project_task set remaining_hours=remaining_hours + %s where id=%s',
                       (hours, line.task_id.id))
            res = super(HrAnalyticTimesheet, self).unlink(cr, uid, line.id, context=context)
            self._trigger_projects(cr, uid, [task_id], context=context)
        return res

    def create(self, cr, uid, vals, context=None):
        if vals.get('task_id'):
            self._set_remaining_hours_create(cr, uid, vals, context)
        return super(HrAnalyticTimesheet, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        self._set_remaining_hours_write(cr, uid, ids, vals, context=context)
        return super(HrAnalyticTimesheet, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        return self._set_remaining_hours_unlink(cr, uid, ids, context)
        
