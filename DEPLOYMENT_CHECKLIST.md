
# Online deployment checklist — private business

1. Create a PostgreSQL database with your hosting provider.
2. Deploy this folder as a Python web service.
3. Set SECRET_KEY to a long random value.
4. Set DATABASE_URL to the PostgreSQL connection string.
5. Set COOKIE_SECURE to 1 when HTTPS is enabled.
6. Open the website and sign in with the initial Admin account.
7. Immediately change the Admin password.
8. Disable the sample employee account.
9. Create individual accounts for your actual employees.
10. Test the workflow: Admin creates job → employee receives it → employee acknowledges → employee selects status/comment → Admin verifies.
11. Enable database backups.

The package contains the application. A public Internet URL requires a hosting/database account.
