# Company verification API

All endpoints are under `/api` and use the existing Bearer JWT authentication.

## Employer flow

1. Upload the business license image with `POST /api/company/me/verification-document`
   as multipart form data (`file`). JPG and PNG are accepted, up to the configured
   upload limit.
2. Submit the tax code with `POST /api/company/me/verification`:

   ```json
   { "tax_code": "0301363748" }
   ```

3. Check `GET /api/company/me` for the status and rejection reason. Results are
   delivered through the shared `GET /api/notifications` API.
   A rejected company can upload a corrected document and resubmit.

## Admin flow

- `GET /api/admin/companies/verifications` lists companies in `PENDING`.
- Only employers who submitted a tax code and license image appear in this list.
- `POST /api/admin/companies/{company_id}/verification` approves or rejects:

  ```json
  { "status": "VERIFIED" }
  ```

  ```json
  { "status": "REJECTED", "reason": "Ảnh giấy phép chưa rõ thông tin." }
  ```

Only users with role `admin` can access these endpoints. A decision creates a
company verification notification for the employer. Rejection requires a reason.

## Job publishing

`POST /api/employer/jobs` creates a job for the authenticated employer. If its
company is not `VERIFIED`, the API stores the job as `draft` regardless of the
requested status. Unverified employers cannot submit a draft for review. Updating
a verified company's legal name or tax code resets verification and returns its
pending or published jobs to drafts.

## Database upgrade

For an existing database, run `sql/company_verification_migration.sql` after
creating the existing company table. Fresh databases get the new columns through
SQLAlchemy model creation.
