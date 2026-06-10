# SCMXPertLite

SCMXPertLite is a lightweight shipment tracking platform with role-based user access, API-first backend design, and MongoDB persistence.

## Tech Stack
- Python + FastAPI: backend REST APIs
- MongoDB Atlas: primary data store
- JWT Authentication: stateless secure login sessions
- Git + GitHub: version control and collaboration
- VS Code + Postman/Thunder Client: developer productivity and API testing

## Architecture (High Level)
- Client calls FastAPI REST endpoints.
- FastAPI validates input, authorizes users by role, and reads/writes MongoDB.
- MongoDB stores users, logins, sensor_data, and shipments collections.
- JWT tokens protect private routes and enforce access control.

## Branch Strategy
- `main`: stable production-ready code
- `dev`: integration branch for active development
- `feature/*`: feature-specific branches merged into `dev`

## Environment Setup
1. Create and activate virtual environment:
   - Windows PowerShell: `python -m venv .venv` then `.venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Add required `.env` values:
   - `MONGODB_URL`
   - `MONGODB_DB_NAME`
   - `JWT_SECRET_KEY`
   - `JWT_EXPIRE_MINUTES`
   - `JWT_ALGORITHM`
   - `DEFAULT_ROLE`
   - `USERS_COLLECTION_NAME`
   - `LOGINS_COLLECTION_NAME`
   - `SENSOR_DATA_COLLECTION_NAME`
   - `SHIPMENTS_COLLECTION_NAME`
4. To use Google reCAPTCHA on the login page, create a reCAPTCHA v2 checkbox site in Google reCAPTCHA Admin and add:
   - `RECAPTCHA_SITE_KEY`
   - `RECAPTCHA_SECRET_KEY`
   If either value is missing, the app falls back to the built-in local math CAPTCHA.

## Run
- `python main.py`

## Production Notes
- The built-in authentication rate limiter is process-local. For multi-worker or deployed production use, replace it with a shared store such as Redis so limits apply consistently across instances.
- Static frontend files currently use manual query-string cache versions. For production builds, use a single release/version value or hashed asset filenames so browser cache busting is predictable.
