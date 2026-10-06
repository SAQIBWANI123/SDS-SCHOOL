def migrate(cr, version):
    """The 'Promoted' student status was replaced by the promotion wizard:
    promoted students simply stay enrolled in their new class."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'school_student' AND column_name = 'state'
    """)
    if cr.fetchone():
        cr.execute("UPDATE school_student SET state = 'enrolled' WHERE state = 'promoted'")
