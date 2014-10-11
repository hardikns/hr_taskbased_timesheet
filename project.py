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

from openerp.osv import fields, osv
from openerp import tools

class project(osv.Model):
    def map_tasks(self, cr, uid, old_project_id, new_project_id, context=None):
        """ copy and map tasks from old to new project """
        if context is None:
            context = {}
        map_task_id = {}
        map_phase_id = {}
        task_obj = self.pool.get('project.task')
        phase_obj = self.pool.get('project.phase')
        proj = self.browse(cr, uid, old_project_id, context=context)
        for phase in proj.phase_ids:
            map_phase_id[phase.id] = phase_obj.copy(cr, uid, phase.id, {'project_id':new_project_id,
                                                                        'task_ids':[],
                                                                        'name':phase.name}, 
                                          context=context)
        for task in proj.tasks:
            map_task_id[task.id] =  task_obj.copy(cr, uid, task.id, 
                                                  {'project_id':new_project_id, 
                                                    'phase_id':map_phase_id[task.phase_id.id]}, 
                                                  context=context)
        task_obj.duplicate_task(cr, uid, map_task_id, context=context)
        return True

    def copy(self, cr, uid, ids, default=None, context=None):
        if context is None:
            context = {}
        if default is None:
            default = {}
        default['phase_ids'] = []    
        res = super(project, self).copy(cr, uid, ids, default, context)
        return res

project()	