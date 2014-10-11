# -*- encoding: utf-8 -*-
##############################################################################
#
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
{'name' : 'Task Based Timesheets',
 'version' : '0.8',
 'author' : 'Msys',
 'maintainer': 'Msys',
 'category': 'Human Resources',
 'depends' : ['hr_timesheet_sheet','hr_timesheet','project','project_long_term'],
 'description': """
 This module is inspired by and based on modules hr_timesheet_task and timesheet_task 
 provided by community. It combines the functionality provided by the 2 modules and
 enhances the functionality provided by them. 
 
 Replace project.task.work items linked to task
                   with hr.analytic.timesheet
 
 Provides ability to report timesheet by Project Tasks.                   
                   
                   """,
 'website': 'http://www.msys-tech.com',
 'data': [
        'hr_timesheet_sheet_view.xml', 
        'hr_analytic_timesheet_view.xml',
        'project_task_view.xml'
        ],
 'js' : ['static/src/js/*.js'],
 'css': ['static/src/css/*.css',],
 'qweb': ['static/src/xml/*.xml'],
 'demo': [],
 'test': [],
 'installable': True,
 'images' : [],
 'auto_install': False,
 'license': 'AGPL-3',
 'application': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
