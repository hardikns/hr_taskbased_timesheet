# -*- coding: utf-8 -*-
##############################################################################
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

from openerp.osv import osv, orm, fields
from openerp.tools.translate import _
from openerp import SUPERUSER_ID

TASK_WATCHERS = ['work_ids', 'remaining_hours', 'effective_hours', 'planned_hours', 'state', 'name']
TIMESHEET_WATCHERS = ['unit_amount', 'product_uom_id', 'account_id', 'task_id', 'state']

class ProjectTask(orm.Model):
    _inherit = "project.task"
    _name = "project.task"

    def _progress_rate(self, cr, uid, ids, names, arg, context=None):
        """TODO improve code taken for OpenERP"""
        res = {}
        cr.execute("""SELECT ts.task_id, COALESCE(SUM(al.unit_amount),0)
                        FROM account_analytic_line al, 
                             hr_analytic_timesheet ts
                      WHERE ts.task_id IN %s
                      and ts.line_id = al.id
                      and ts.state = 'done'
                      GROUP BY ts.task_id""", (tuple(ids),))

        hours = dict(cr.fetchall())
        cr.execute("""SELECT ts.task_id, COALESCE(SUM(al.unit_amount),0)
                        FROM account_analytic_line al, 
                             hr_analytic_timesheet ts
                      WHERE ts.task_id IN %s
                      and ts.line_id = al.id
                      and ts.state <> 'done'
                      GROUP BY ts.task_id""", (tuple(ids),))

        pending_hours = dict(cr.fetchall())
        for task in self.browse(cr, uid, ids, context=context):
            res[task.id] = {}
            res[task.id]['pending_hours'] = pending_hours.get(task.id,0.0)
            res[task.id]['effective_hours'] = hours.get(task.id, 0.0)
            res[task.id]['total_hours'] = (task.remaining_hours or 0.0) + hours.get(task.id, 0.0) + pending_hours.get(task.id,0.0)
            res[task.id]['delay_hours'] = res[task.id]['total_hours'] - task.planned_hours
            res[task.id]['progress'] = 0.0
            if (task.remaining_hours + hours.get(task.id, 0.0)):
                res[task.id]['progress'] = round(min(100.0 * hours.get(task.id, 0.0) / res[task.id]['total_hours'], 99.99), 2)
            if task.state in ('done', 'cancelled'):
                res[task.id]['progress'] = 100.0
            
        return res


    def _store_set_values(self, cr, uid, ids, fields, context=None):
        # Hack to avoid redefining most of function fields of project.project model
        # This is mainly due to the fact that orm _store_set_values use direct access to database.
        # So when modifiy aa line the _store_set_values as it uses cursor directly to update tasks
        # project triggers on task are not called
        res = super(ProjectTask, self)._store_set_values(cr, uid, ids, fields, context=context)
        for row in self.browse(cr, SUPERUSER_ID, ids, context=context):
            project = row.project_id
            if project:
                project.write({'parent_id': project.parent_id.id})
        return res

    def _get_hr_timesheet_sheet(self, cr, uid, ids, context=None):
        task_ids = []

        for ts in self.browse(cr, uid, ids, context=context):
            cr.execute("""
                    SELECT t.id
                        FROM hr_analytic_timesheet l
                    INNER JOIN account_analytic_line al
                        ON (l.line_id = al.id)
                    INNER JOIN project_task t
                        ON (l.task_id = t.id)
                    WHERE %(date_to)s >= al.date
                        AND %(date_from)s <= al.date
                        AND %(user_id)s = al.user_id
                    GROUP BY t.id""", {'date_from': ts.date_from,
                                        'date_to': ts.date_to,
                                        'user_id': ts.employee_id.user_id.id,})
            task_ids.extend([row[0] for row in cr.fetchall()])
        return task_ids

    def _get_analytic_line(self, cr, uid, ids, context=None):
        result = []
        for res in self.pool.get('hr.analytic.timesheet').read(cr, uid, ids, ['task_id'] , context=context):
            if res['task_id']: result.append(res['task_id'][0])
        return result
        
    def onchange_project(self, cr, uid, ids, project_id, context=None):
        ret = super(ProjectTask, self).onchange_project(cr, uid, ids, project_id, context=context)
        if not 'value' in ret:
            ret.update({'value':{}})
        task = len(ids) and self.browse(cr, uid, ids[0]) or False
        if task and task.phase_id:
            ret['value']['phase_id'] = False
        if project_id:
            res = self.pool.get('project.project').read(cr, uid, [project_id],['members'])
            if len(res):
                members = res[0]['members'] or []
                ret['value']['projmembers'] = members
                ret['value']['user_id'] = False
        return ret
    
    def _member_ids(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for task in self.browse(cr, uid, ids): 
            res[task.id] = []
            if task.project_id:
                res.update({task.id:[x.id for x in task.project_id.members]})
        return res
    
    _columns = {
        'work_ids': fields.one2many('hr.analytic.timesheet', 'task_id', 'Work done'),
        'projmembers': fields.function(_member_ids, type="char", string="Project_members"),
        'user_id': fields.many2one('res.users', 'Assigned to', track_visibility='onchange', domain="[('id','in',projmembers)]"),
        'effective_hours': fields.function(_progress_rate, multi="progress", string='Time Spent (Approved)',
                                           help="Computed using the sum of the approved task work done (timesheet lines "
                                                "associated on this task).",
                                           store={'project.task': (lambda self, cr, uid, ids, c=None: ids, TASK_WATCHERS, 20),
                                                  'hr_timesheet_sheet.sheet': (_get_hr_timesheet_sheet, ['state'], 20),
                                                  'hr.analytic.timesheet': (_get_analytic_line, TIMESHEET_WATCHERS, 20)}),
        'pending_hours': fields.function(_progress_rate, multi="progress", string='Time Spent (Pending)',
                                           help="Computed using the sum of the pending task work done (timesheet lines "
                                                "associated on this task but not approved).",
                                           store={'project.task': (lambda self, cr, uid, ids, c=None: ids, TASK_WATCHERS, 20),
                                                  'hr_timesheet_sheet.sheet': (_get_hr_timesheet_sheet, ['state'], 20),
                                                  'hr.analytic.timesheet': (_get_analytic_line, TIMESHEET_WATCHERS, 20)}),
        'delay_hours': fields.function(_progress_rate, multi="progress", string='Deduced Hours',
                                       help="Computed as difference between planned hours by the project manager "
                                            "and the total hours of the task.",
                                       store={'project.task': (lambda self, cr, uid, ids, c=None: ids, TASK_WATCHERS, 20),
                                              'hr_timesheet_sheet.sheet': (_get_hr_timesheet_sheet, ['state'], 20),
                                              'hr.analytic.timesheet': (_get_analytic_line, TIMESHEET_WATCHERS, 20)}),
        'total_hours': fields.function(_progress_rate, multi="progress", string='Total Time',
                                       help="Computed as: Time Spent + Remaining Time.",
                                       store={'project.task': (lambda self, cr, uid, ids, c=None: ids, TASK_WATCHERS, 20),
                                              'hr_timesheet_sheet.sheet': (_get_hr_timesheet_sheet, ['state'], 20),
                                              'hr.analytic.timesheet': (_get_analytic_line, TIMESHEET_WATCHERS, 20)}),
        'progress': fields.function(_progress_rate, multi="progress", string='Progress', type='float', group_operator="avg",
                                    help="If the task has a progress of 99.99% you should close the task if it's "
                                         "finished or reevaluate the time",
                                    store={'project.task': (lambda self, cr, uid, ids, c=None: ids, TASK_WATCHERS, 20),
                                           'hr_timesheet_sheet.sheet': (_get_hr_timesheet_sheet, ['state'], 20),
                                           'hr.analytic.timesheet': (_get_analytic_line, TIMESHEET_WATCHERS, 20)})
    }
    _defaults = {  
        'user_id': False,  
    }

    def write(self, cr, uid, ids, vals, context=None):
        res = super(ProjectTask, self).write(cr, uid, ids, vals, context=context)
        if vals.get('project_id'):
            ts_obj = self.pool.get('hr.analytic.timesheet')
            project_obj = self.pool.get('project.project')
            project = project_obj.browse(cr, uid, vals['project_id'], context=context)
            account_id = project.analytic_account_id.id
            for task in self.browse(cr, uid, ids, context=context):
                ts_obj.write(cr, uid, [w.id for w in task.work_ids], {'account_id': account_id}, context=context)
        return res

    def action_close(self, cr, uid, ids, context=None):
        for task in self.browse(cr, uid, ids, context):
            if task.pending_hours:
                raise osv.except_osv(_("Warning!"), _("There are pending timesheets for the Task.\nPlease delete them or approve them."))
        return super(ProjectTask, self).action_close(cr, uid, ids, context=context)

"""class AccountAnalyticLine(orm.Model):
    _inhert = 'account.analytic.line'
    _name = 'account.analytic.line'
    _columns = {
        'ts_ids': fields.one2many('hr.analytic.timesheet', 'line_id' ,'Timesheets')
    }
"""
class analytic_account(orm.Model):
    _inherit = 'account.analytic.account'

    def _is_proj_member(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        user_id = context.get('check_uid',uid)
        for aa in self.browse(cr, uid, ids): 
            if aa.project_id.members:
                res.update({aa.id: user_id in [x.id for x in aa.project_id.members]})
            else:
                res.update({aa.id:False})
        return res
        
    def _is_proj_member_srch(self, cr, uid, model, field_name, criteria, context=None):
        user_id = context.get('check_uid',uid)
        cr.execute("""
            select analytic_account_id
            from project_user_rel pur, project_project p
            where pur.uid = %s and pur.project_id = p.id
            """ % user_id)
        return [('id','in',[x[0] for x in cr.fetchall()])]
        
    def _get_related_project_id(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        project_pool = self.pool.get('project.project')
        for aa_id in ids: 
            proj_id = project_pool.search(cr, uid, [('analytic_account_id','=',aa_id)])
            res.update({aa_id:len(proj_id) and proj_id[0] or False})

        return res 
    
    _columns = {
        'project_id': fields.function(_get_related_project_id, type="many2one", relation="project.project", string="Related Project", store=True),
        'is_proj_member': fields.function(_is_proj_member, type="boolean", string="Is User Project Member?", fnct_search=_is_proj_member_srch),
    }
        
