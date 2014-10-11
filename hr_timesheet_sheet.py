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

from openerp.osv import fields, osv
from openerp import SUPERUSER_ID

class hr_timesheet_sheet(osv.osv):
    _name = "hr_timesheet_sheet.sheet"
    _inherit = "hr_timesheet_sheet.sheet"
    
    def _is_manager(self,cr,uid,ids,name, arg, context=None):
        res = {}
        for sheet_id in ids:
            res.update({sheet_id:self.is_manager(cr, uid, ids)})
        return res
        
    def is_manager(self,cr,uid,ids,context=None):
        if uid == SUPERUSER_ID:
            return True
        mgr_emp = self.pool.get('hr.employee').search(cr, uid, [('user_id','=',uid)],context=context)
        emp_id = self.read(cr, uid, ids[0], ['employee_id'])['employee_id']
        if mgr_emp and emp_id:
            child_emps = self.pool.get('hr.employee').search(cr, uid, [('id','child_of',mgr_emp[0]),('id','!=',mgr_emp[0])], context=context)
            if emp_id[0] in child_emps:
                return True
        return False

    def _is_manager_srch(self, cr, uid, model, field_name, criteria, context=None):
        emp_pool = self.pool.get('hr.employee')
        mgr_emp = emp_pool.search(cr, uid, [('user_id','=',uid)],context=context)
        ret = []
        if mgr_emp:
            child_emps = emp_pool.search(cr, uid, [('id','child_of',mgr_emp[0]),('id','!=',mgr_emp[0])], context=context)
            if child_emps:
                ret = self.search(cr, uid, [('employee_id','in',child_emps)],context=context)
        return [('id','in',ret)]        

    
    _columns = {
        'manager_id': fields.related('employee_id', 'parent_id', type="many2one", relation="hr.employee", store=True, string="Manager", required=False, readonly=True),
        'manager_uid' : fields.related('manager_id', 'user_id', type="many2one", relation="res.users", store=True, string="Manager User", required=False, readonly=True),
        'is_uid_manager': fields.function(_is_manager, method=True, string='Is Manager', type="boolean", fnct_search=_is_manager_srch),
    }
    
    TSS_ERROR = "Error: Timesheet dates are not within the date range or hours are negative"
    def _check_timesheets(self, cr, uid, ids, context=None): 
        for tss in self.browse(cr, uid, ids, context=context):
            date_from = tss.date_from
            date_to = tss.date_to 
            for ts in tss.timesheet_ids:
                if ts.unit_amount < 0.0 or ts.date < date_from or ts.date > date_to:
                    return False
        return True
    
    _constraints = [(_check_timesheets, TSS_ERROR, ['timesheet_ids']), ] 
    
    def unlink(self, cr, uid, ids, context=None):
        for tss in self.browse(cr, uid, ids, context=context):
            ts_ids = [ts.id for ts in tss.timesheet_ids]
            self.pool.get('hr.analytic.timesheet').unlink(cr, uid, ts_ids, context=context)
        res = super(hr_timesheet_sheet, self).unlink(cr, uid, ids, context=context)
        return res 
    
