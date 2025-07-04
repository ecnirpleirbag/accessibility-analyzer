import sqlite3

conn = sqlite3.connect('scans.db')
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    alt_issues INTEGER,
    heading_issues INTEGER,
    form_label_issues INTEGER,
    aria_issues INTEGER,
    axe_critical INTEGER,
    axe_serious INTEGER,
    axe_moderate INTEGER,
    axe_minor INTEGER
)
''')
conn.commit()
conn.close()
print('Database initialized.') 