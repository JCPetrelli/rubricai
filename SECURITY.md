# Security and privacy

Rubricai runs locally. It sends nothing over the network: it reads Contacts.app through `osascript`, Apple Mail's index and WhatsApp Desktop's databases with SQLite, and writes files only where you tell it to.

Those files hold personal data about other people: exports, plans, candidate lists, logs and vCard backups. Keep them out of version control (`.gitignore` covers the defaults) and delete them when you are done.

Reading Mail's index needs Full Disk Access for your terminal. Writing to Contacts needs the Automation permission for Contacts. Grant neither to a terminal you do not trust.

If you find a way for a plan or an export to run unintended code, or for the tools to leak data, don't open a public issue. Email info@jacopocastellano.com with the details. You'll get a reply within a week.
