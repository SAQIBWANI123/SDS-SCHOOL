{
    'name': 'SDS SCHOOL MANAGEMENT SYSTEM',
    'version': '19.0.2.0.0',
    'category': 'Education',
    'author': 'SmartDeskSolution',
    'maintainer': 'SmartDeskSolution',
    'website': 'https://www.smartdesksolution.com',
    'support': 'info@smartdesksolution.com',
    'summary': 'Admissions, fees with partial payments, attendance, exams, library, notices and a live dashboard',
    'description': """
CampusPulse - School Management Suite for Odoo 19
=================================================
Developed by SmartDeskSolution | www.smartdesksolution.com | info@smartdesksolution.com

Highlights
----------
- Live dashboard: enrolment, attendance, fee collection, overdue fees, admissions, notices, exams, birthdays
- Admissions with waitlist, online application form and one-click enrolment
- Fees: structures, bulk fee generation, partial payments, receipts, overdue tracking
- Attendance registers with "Mark all present" and one register per class per day
- Exams: workflow, auto-generated report cards, grading scale, class rank
- Bulk student promotion / graduation wizard
- Conduct and achievement log with conduct score
- Notice board
- Library with fines, renewals and overdue automation
- Transport routes and vehicles, timetables, parent portal, PDF reports
    """,
    'depends': ['base', 'mail', 'website', 'portal'],
    'data': [
        'security/school_security.xml',
        'security/ir.model.access.csv',
        'data/school_sequence_data.xml',
        'data/school_data.xml',
        'views/menus.xml',
        'views/admission_views.xml',
        'views/dashboard_views.xml',
        'views/academic_year_views.xml',
        'views/grade_level_views.xml',
        'views/school_class_views.xml',
        'views/subject_views.xml',
        'views/conduct_views.xml',
        'views/student_views.xml',
        'views/teacher_views.xml',
        'views/parent_views.xml',
        'views/attendance_views.xml',
        'views/exam_views.xml',
        'views/timetable_views.xml',
        'views/fee_views.xml',
        'views/transport_views.xml',
        'views/library_views.xml',
        'views/notice_views.xml',
        'views/portal_templates.xml',
        'report/school_reports.xml',
        'report/report_student_id_card.xml',
        'report/report_student_report_card.xml',
        'report/report_fee_receipt.xml',
    ],
    'demo': [
        'demo/school_demo_data.xml',
        'demo/school_demo_extra.xml',
    ],
    'images': [
        'static/description/icon.png',
        'static/description/banner.png',
    ],
    'assets': {
        'web.assets_backend': [
            'SDS_school_management_system/static/src/scss/school_dashboard.scss',
            'SDS_school_management_system/static/src/js/school_dashboard.js',
            'SDS_school_management_system/static/src/xml/school_dashboard.xml',
        ],
        'web.assets_frontend': [
            'SDS_school_management_system/static/src/css/portal.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
