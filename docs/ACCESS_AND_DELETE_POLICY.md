# Access And Delete Policy

## Auth Style
- Primary auth endpoints are under `/user/*`.
- Login token endpoint is `POST /user/login`.
- Protected endpoints use `Authorization: Bearer <token>`.

## Role Permissions
- `customer`: regular user access only.
- `admin`: can list users and update user roles.
- `super_admin`: has admin capabilities plus destructive admin actions.

Current admin routes:
- `GET /api/admin/users`: `admin` and `super_admin`.
- `PATCH /api/admin/users/{user_id}/role`: `admin` and `super_admin`.
- `DELETE /api/admin/users/{user_id}`: `super_admin` only.

## Soft Delete Rules
- Shipment delete is soft delete.
- Device delete is soft delete.
- Soft delete sets:
  - `is_deleted: true`
  - `deleted_at: <utc datetime>`
  - `updated_at: <utc datetime>`

### Impact
- Soft-deleted records stay in MongoDB.
- Normal list/get/update flows filter out records where `is_deleted == true`.
- This preserves auditability and allows future recovery tooling.
