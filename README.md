# SCMXPertLite

SCMXPertLite is a lightweight shipment tracking platform with role-based user access, API-first backend design, and MongoDB persistence.

## Tech Stack
- Python + FastAPI: backend REST APIs
- MongoDB Atlas: primary data store
- JWT Authentication: stateless secure login sessions
- Kafka: device telemetry producer and consumer for data streaming
- Git + GitHub: version control and collaboration
- VS Code + Postman/Thunder Client: developer productivity and API testing

## Architecture (High Level)
- Client calls FastAPI REST endpoints.
- FastAPI validates input, authorizes users by role, and reads/writes MongoDB.
- MongoDB stores users, logins, sensor_data, and shipments collections.
- Kafka streams device events into the consumer, which stores raw sensor data and updates the device dashboard collection.
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
   - `KAFKA_BOOTSTRAP_SERVERS`
   - `KAFKA_DEVICE_TOPIC`
   - `KAFKA_CONSUMER_GROUP`
4. To use Google reCAPTCHA on the login page, create a reCAPTCHA v2 checkbox site in Google reCAPTCHA Admin and add:
   - `RECAPTCHA_SITE_KEY`
   - `RECAPTCHA_SECRET_KEY`
   If either value is missing, the app falls back to the built-in local math CAPTCHA.

## Run
- `python main.py`

## Kafka Device Streaming
- Start Kafka locally or point `KAFKA_BOOTSTRAP_SERVERS` at your broker.
- Run the consumer: `python -m backend.kafka.consumer`
- Publish a sample device event: `python -m backend.kafka.producer`
- The consumer writes each event to `sensor_data` and upserts the latest device state into `devices`.

## Password Reset
- Login includes a forgot-password flow.
- Configure SMTP with `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_USE_TLS` to email reset tokens.
- Without SMTP settings, the reset endpoint returns the token so the flow can be tested locally and the login page fills it into the reset form.
- For Gmail, create an app password and use it as `SMTP_PASSWORD`; normal account passwords usually will not work.

## Production Notes
- The built-in authentication rate limiter is process-local. For multi-worker or deployed production use, replace it with a shared store such as Redis so limits apply consistently across instances.
- Static frontend files currently use manual query-string cache versions. For production builds, use a single release/version value or hashed asset filenames so browser cache busting is predictable.
